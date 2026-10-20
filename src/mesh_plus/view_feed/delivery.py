"""Explicit view-feed negotiation over unchanged state Delivery messages.

No source collection or native event replay is introduced here. Snapshot/proof
requests remain full original replies; only an opted-in subscription uses feed
packets. Each served connection and subscription owns independent feed state.
"""

import asyncio
import contextlib
import copy
import secrets
import sys
from dataclasses import asdict

from ..bridge import Bridge, Publication
from ..client import Client
from ..protocol import MAX_CONTROL, check, decode_json, encode
from ..state import check_binding, validate_bridge
from ..transport import LineChannel, boottime_ms, finish_owned, within_deadline
from .budget import FeedBudget
from .core import FeedEncoder, FeedLimits, FeedReceiver
from .protocol import FEED_PROTOCOL, json_size, validate_packet
from .wire import CreditOwner, FeedWireCodec


def _selector(value):
    check(type(value) is dict, "view_feed_selector")
    json_size(value, maximum=4096)
    raw = encode(value)
    check(len(raw) <= 4096, "view_feed_selector_capacity")
    result = decode_json(raw, 4096)
    check(result == value, "view_feed_selector")
    return result


def _limits(value):
    check(type(value) is dict and set(value) == set(asdict(FeedLimits())), "view_feed_limits")
    try:
        return FeedLimits(**value)
    except (TypeError, ValueError) as error:
        raise ValueError("view_feed_limits") from error


def _narrow(configured, requested):
    left, right = asdict(configured), asdict(requested)
    check(set(left) == set(right), "view_feed_limits")
    return FeedLimits(**{key: min(left[key], right[key]) for key in left})


def _json_heap(value, depth=0):
    check(depth <= 64, "view_feed_tree_depth")
    total = sys.getsizeof(value)
    if isinstance(value, dict):
        total += sum(sys.getsizeof(key) + _json_heap(child, depth + 1) for key, child in value.items())
    elif isinstance(value, list):
        total += sum(_json_heap(child, depth + 1) for child in value)
    return total


class _QueuedPayload(dict):
    """Queue-owned JSON; retained frames/errors retain their reservation."""

    def __init__(self, value, credit):
        super().__init__(value)
        self._feed_credit = credit

    def __deepcopy__(self, memo):
        return copy.deepcopy(dict(self), memo)


class _FeedPublication(Publication):
    """Keep the packet and its exact reset target funded through actual send."""

    def __init__(self, message, epoch, barrier):
        super().__init__(message.payload, epoch, barrier)
        object.__setattr__(self, "message", message)

    def __del__(self):
        message = getattr(self, "message", None)
        if message is not None:
            message.close()


class _OwnedFrame(dict):
    """A full Delivery frame owning the independently admitted target result."""

    def __init__(self, frame, applied):
        super().__init__(frame, payload=applied.candidate)
        self.applied = applied

    def __del__(self):
        applied = getattr(self, "applied", None)
        if applied is not None:
            applied.close()

    def __deepcopy__(self, memo):
        return copy.deepcopy(dict(self), memo)


class _FeedPublisher:
    def __init__(self, adapter, profile, selector, limits, token, token_scheme):
        self.adapter, self.state_profile = adapter, profile
        self.host, self.source, self.profile = adapter.host, adapter.source, adapter.profile
        self.capabilities = adapter.capabilities
        self.codec = profile.bind(self.host, self.source)
        check_binding(self.codec, self.host, self.source, self.profile)
        self.selector, self.limits = _selector(selector), limits
        self.token, self.token_scheme = token, token_scheme
        self.negotiated = False
        self.budget = FeedBudget(limits)

    def _ready(self, nonce):
        return {"protocol": FEED_PROTOCOL, "kind": "ready", "nonce": nonce,
                "hostId": self.host, "sourceId": self.source, "profile": self.profile,
                "contractDigest": self.state_profile.descriptor.contract_digest,
                "selector": _selector(self.selector), "limits": asdict(self.limits)}

    async def snapshot(self, parameters):
        if type(parameters) is dict and "viewFeed" in parameters:
            check(not self.negotiated and set(parameters) == {"viewFeed"}, "view_feed_negotiation")
            requested = parameters["viewFeed"]
            check(type(requested) is dict and
                  set(requested) == {"protocol", "nonce", "selector", "limits"} and
                  requested["protocol"] == FEED_PROTOCOL, "view_feed_negotiation")
            nonce = requested["nonce"]
            check(type(nonce) is str and len(nonce) == 32 and
                  all(c in "0123456789abcdef" for c in nonce), "view_feed_nonce")
            check(_selector(requested["selector"]) == self.selector, "view_feed_selector")
            self.limits = _narrow(self.limits, _limits(requested["limits"]))
            self.budget.narrow(self.limits)
            self.negotiated = True
            return self._ready(nonce)
        return await self.adapter.snapshot(parameters)

    async def proof(self, parameters):
        return await self.adapter.proof(parameters)

    def validate(self, payload):
        if isinstance(payload, dict) and payload.get("protocol") == FEED_PROTOCOL:
            if payload.get("kind") == "ready":
                check(payload == self._ready(payload.get("nonce")), "view_feed_ready")
            else:
                validate_packet(payload, self.limits)
        else:
            self.adapter.validate(payload)

    async def watch(self):
        check(self.negotiated, "view_feed_not_negotiated")
        encoder = FeedEncoder(self.state_profile, self.codec, selector=self.selector,
                              limits=self.limits, budget=self.budget,
                              token=self.token, token_scheme=self.token_scheme)
        iterator = self.adapter.watch().__aiter__()
        message = publication = result = None
        try:
            async for publication in iterator:
                message = encoder.encode(publication.payload)
                if message is None:
                    continue
                result = _FeedPublication(message, publication.epoch, publication.barrier)
                # Ownership moves to the publication, which can outlive this
                # generator while Bridge drains or coalesces the output.
                message = None
                yield result
                result = publication = None
        finally:
            if message is not None:
                message.close()
            encoder.close()
            try:
                await finish_owned(asyncio.ensure_future(iterator.aclose()))
            finally:
                encoder = iterator = publication = message = result = None

    def reset_publication(self, publication):
        check(isinstance(publication, _FeedPublication), "view_feed_publication")
        # A message pins its own target: the producer may already have advanced
        # to a newer generation while this publication waits for byte credit.
        message = publication.message.replacement()
        return _FeedPublication(message, publication.epoch, publication.barrier)


class ViewFeedBridge:
    """Opt-in Bridge facade; its setup flag is scoped to one served channel."""

    def __init__(self, adapter, *, profile, selector=None, limits=None,
                 token=None, token_scheme=None, heartbeat_interval=5, credit_timeout=15):
        check(adapter.profile == profile.descriptor.profile_id, "view_feed_profile")
        self.adapter, self.profile = adapter, profile
        self.selector = _selector({} if selector is None else selector)
        self.limits = FeedLimits() if limits is None else limits
        self.token, self.token_scheme = token, token_scheme
        self.heartbeat_interval, self.credit_timeout = heartbeat_interval, credit_timeout

    async def serve(self, channel):
        wire = None
        try:
            adapter = _FeedPublisher(self.adapter, self.profile, self.selector, self.limits,
                                     self.token, self.token_scheme)
            check(isinstance(channel, LineChannel) and channel.codec is None, "view_feed_carrier")
            wire = FeedWireCodec(adapter.budget)
            channel.codec = wire
            await Bridge(adapter, heartbeat_interval=self.heartbeat_interval,
                         credit_timeout=self.credit_timeout).serve(channel)
        finally:
            try:
                await finish_owned(asyncio.create_task(channel.close()))
            finally:
                if wire is not None:
                    wire.close()
                adapter = channel = self = None


class _WireAdmission:
    _mesh_payload_admission = 1

    def __init__(self, profile, codec, selector, limits):
        self.profile, self.codec = profile, codec
        self.selector, self.limits = selector, limits
        self.budget = FeedBudget(limits)

    def admit_payload(self, payload, *, encoded_bytes, frame=None):
        # Transfer the prepaid decoded frame's physical owner into its queued
        # payload. The original frame and payload can overlap without refunding
        # or taking a second credit for the same parsed graph.
        credit = getattr(frame, "_feed_credit", None)
        if credit is None:
            credit = CreditOwner(self.budget.reserve(encoded=encoded_bytes,
                                                       heap=_json_heap(payload) + sys.getsizeof(payload) + 1024))
        try:
            self(payload)
            result = _QueuedPayload(payload, credit)
            return result
        finally:
            payload = credit = None

    def __call__(self, payload):
        if isinstance(payload, dict) and payload.get("protocol") == FEED_PROTOCOL:
            if payload.get("kind") == "ready":
                check(set(payload) == {"protocol", "kind", "nonce", "hostId", "sourceId", "profile",
                                      "contractDigest", "selector", "limits"}, "view_feed_ready")
                check(len(encode(payload)) <= MAX_CONTROL, "view_feed_ready_capacity")
            else:
                validate_packet(payload, self.limits)
        else:
            validate_bridge(self.profile, self.codec, payload)


class ViewFeedSubscription:
    """A validating subscription returning ordinary full Delivery data frames."""

    def __init__(self, owner, subscription):
        self.owner, self.subscription = owner, subscription
        self.receiver = FeedReceiver(owner.profile, owner.state_codec,
                                     selector=owner.selector, limits=owner.limits, budget=owner.budget)
        self.closed = False
        self._close_started = False
        self._close_task = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        frame = packet = applied = None
        try:
            frame = await anext(self.subscription)
            check(not self.closed and not self.owner.closed, "view_feed_closed")
            if frame["kind"] == "control":
                if frame["control"] == "gap":
                    self.receiver.mark_gap()
                return frame
            check(frame["kind"] == "data", "view_feed_data")
            packet = frame["payload"]
            applied = self.receiver.apply(packet)
            check(not self.closed and not self.owner.closed, "view_feed_closed")
            result = _OwnedFrame(frame, applied)
            applied = None
            return result
        except BaseException:
            if applied is not None:
                applied.close()
            self.retire()
            with contextlib.suppress(Exception):
                await self.close()
            raise
        finally:
            frame = packet = applied = None

    def retire(self):
        self.closed = True
        self.receiver.close()

    async def close(self):
        self.retire()
        if not self._close_started:
            self._close_started = True
            self._close_task = asyncio.create_task(self.subscription.close())
        task = self._close_task
        if task is None:
            return
        try:
            await finish_owned(task)
        finally:
            if task.done():
                self.owner._subscriptions.discard(self)
                self._close_task = None
            task = None


class ViewFeedChange:
    """An owned application change/reset; no currentness or action authority."""

    def __init__(self, frame):
        self._frame = frame

    @property
    def kind(self):
        return self._frame.applied.kind

    @property
    def revision(self):
        return self._frame.applied.revision

    @property
    def upserts(self):
        return self._frame.applied.upserts

    @property
    def removals(self):
        return self._frame.applied.removals

    @property
    def order(self):
        return self._frame.applied.order

    @property
    def candidate(self):
        return self._frame["payload"]

    def close(self):
        self._frame = None


class ViewFeedClient:
    """Explicitly negotiated Client facade accepted by the ordinary Reader."""

    def __init__(self, client, profile, codec, selector, limits, admission, wire):
        self.client, self.profile, self.state_codec = client, profile, codec
        self.selector, self.limits = selector, limits
        self.budget = admission.budget
        self.wire = wire
        self._subscriptions = set()
        self.closed = False
        self._close_task = None

    @classmethod
    async def connect(cls, channel, *, host, source, profile, selector=None, limits=None, timeout=3):
        client = None
        wire = None
        try:
            check(type(timeout) in (int, float) and 0 < timeout <= 15, "view_feed_setup_budget")
            deadline = boottime_ms() + int(timeout * 1000)
            selector = _selector({} if selector is None else selector)
            limits = FeedLimits() if limits is None else limits
            codec = profile.bind(host, source)
            check_binding(codec, host, source, profile.descriptor.profile_id)
            admission = _WireAdmission(profile, codec, selector, limits)
            check(isinstance(channel, LineChannel) and channel.codec is None, "view_feed_carrier")
            wire = FeedWireCodec(admission.budget)
            channel.codec = wire
            client = await Client.connect(channel, host=host, source=source,
                                          profile=profile.descriptor.profile_id,
                                          codec=admission,
                                          required=("snapshot", "proof", "subscribe"), timeout=timeout)
            nonce = secrets.token_hex(16)
            parameters = {"viewFeed": {"protocol": FEED_PROTOCOL, "nonce": nonce,
                                       "selector": selector, "limits": asdict(limits)}}
            remaining = deadline - boottime_ms()
            check(remaining > 0, "view_feed_setup_deadline")
            ready = await within_deadline(client.request("snapshot", parameters, timeout_ms=remaining), deadline)
            check(ready.get("protocol") == FEED_PROTOCOL and ready.get("kind") == "ready" and
                  ready.get("nonce") == nonce and ready.get("selector") == selector and
                  ready.get("hostId") == host and ready.get("sourceId") == source and
                  ready.get("profile") == profile.descriptor.profile_id and
                  ready.get("contractDigest") == profile.descriptor.contract_digest, "view_feed_ready_binding")
            agreed = _limits(ready["limits"])
            check(asdict(_narrow(limits, agreed)) == asdict(agreed), "view_feed_limit_enlargement")
            check(boottime_ms() < deadline, "view_feed_setup_deadline")
            admission.limits = agreed
            admission.budget.narrow(agreed)
            return cls(client, profile, codec, selector, agreed, admission, wire)
        except BaseException:
            try:
                if client is not None:
                    await finish_owned(asyncio.create_task(client.close()))
                else:
                    await finish_owned(asyncio.create_task(channel.close()))
            finally:
                if wire is not None:
                    wire.close()
            raise
        finally:
            client = channel = None

    @property
    def guard(self):
        return self.client.guard

    @property
    def channel(self):
        return self.client.channel

    @property
    def codec(self):
        return self.state_codec.validate_bridge

    def inspect(self):
        return {**self.client.inspect(), "viewFeed": self.budget.inspect()}

    def rotation_due(self):
        return self.client.rotation_due()

    async def request(self, *args, **kwargs):
        check(not self.closed, "view_feed_closed")
        return await self.client.request(*args, **kwargs)

    async def subscribe(self):
        check(not self.closed, "view_feed_closed")
        raw = await self.client.subscribe()
        if self.closed:
            await finish_owned(asyncio.create_task(raw.close()))
            check(False, "view_feed_closed")
        sub = ViewFeedSubscription(self, raw)
        self._subscriptions.add(sub)
        return sub

    async def changes(self):
        sub = await self.subscribe()
        frame = event = None
        try:
            async for frame in sub:
                if frame["kind"] == "data":
                    event = ViewFeedChange(frame)
                    yield event
                    frame = event = None
                else:
                    # Controls are explicit invalidation/liveness messages;
                    # they cannot be mistaken for domain record events.
                    yield frame
                    frame = None
        finally:
            frame = event = None
            await sub.close()

    async def close(self):
        if not self.closed:
            self.closed = True
            subscriptions = tuple(self._subscriptions)
            for sub in subscriptions:
                sub.retire()

            async def cleanup():
                try:
                    await asyncio.gather(*(sub.close() for sub in subscriptions), return_exceptions=True)
                finally:
                    self._subscriptions.clear()
                    try:
                        await self.client.close()
                    finally:
                        self.wire.close()

            self._close_task = asyncio.create_task(cleanup())
        if self._close_task is not None:
            task = self._close_task
            try:
                await finish_owned(task)
            finally:
                if task.done():
                    self._close_task = None
                task = None
