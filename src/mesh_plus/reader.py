"""Fleet composition over independently bound delivery clients."""

import asyncio
import copy
import re
import secrets
import uuid
from dataclasses import dataclass

from .admission import AdmittedResponse
from .client import DeliveryError
from .evidence import clock_domain, digest
from .protocol import check
from .state import check_binding, legacy_codec, resolve_profile, validate_bridge
from .transport import _wait_until, boottime_ms, finish_owned, within_deadline
from .view import _validated_response, remote_expiry


def outcome_code(error):
    if isinstance(error, TimeoutError):
        return "timeout"
    code = getattr(error, "code", "source_unavailable")
    return code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", code) else "source_unavailable"


@dataclass(frozen=True)
class Endpoint:
    host: str
    local: bool
    route_token: str | None
    connect: object
    codec: object = None


@dataclass
class PublicationState:
    sequence: int = 0
    revision: int = 0
    fingerprint: str | None = None


class Reader:
    def __init__(self, domain, endpoints, *, local_host, catalog_revision=None, catalog_check=None, profile=None):
        check(domain in {"tmux", "agent"}, "observer_domain")
        self.profile = resolve_profile(domain, profile)
        self.domain, self.local_host, self.catalog_revision = domain, local_host, catalog_revision
        self.endpoints = tuple(endpoints)
        check(len({endpoint.host for endpoint in self.endpoints}) == len(self.endpoints) and
              1 <= len(self.endpoints) <= 16, "endpoint_scope")
        check(all(endpoint.local == (endpoint.host == local_host) for endpoint in self.endpoints), "endpoint_local_binding")
        check(all((endpoint.route_token is None) == endpoint.local for endpoint in self.endpoints), "endpoint_route_binding")
        check(catalog_revision is not None or [e.host for e in self.endpoints] == [local_host], "catalog_required")
        self._bindings = {}
        for endpoint in self.endpoints:
            if endpoint.codec is not None:
                check_binding(endpoint.codec, endpoint.host, endpoint.codec.source, self.profile.descriptor.profile_id)
                self._bindings[id(endpoint)] = (endpoint.host, endpoint.codec.source, self.profile.descriptor.profile_id)
        self.id = str(uuid.uuid4())
        self.setup_slots = asyncio.Semaphore(4)
        self.catalog_check = catalog_check
        self._clients = {}
        self._totals = self._empty_metrics()
        self._counts = {"connectionAttempts": 0, "connectionsOpened": 0, "connectionsClosed": 0,
                        "connectionFailures": 0, "rotations": 0, "cleanupFailures": 0,
                        "peakConnections": 0, "catalogChecks": 0, "catalogCheckMs": 0}

    @staticmethod
    def _empty_metrics():
        return {"instrumentedConnections": 0, "uninstrumentedConnections": 0,
                "receivedFrames": 0, "sentFrames": 0, "receivedBytes": 0, "sentBytes": 0,
                "operations": {}, "byKind": {"received": {}, "sent": {}},
                "peakClientBufferedBytes": 0, "peakClientBufferedControlBytes": 0,
                "peakSubscriptionQueueFrames": 0, "peakRetainedHandles": 0}

    @staticmethod
    def _merge_metrics(total, client):
        inspection = client.inspect() if callable(getattr(client, "inspect", None)) else {}
        channel = inspection.get("channel") or {}
        measured = "operations" in inspection and "byKind" in channel
        total["instrumentedConnections" if measured else "uninstrumentedConnections"] += 1
        for key in ("receivedFrames", "sentFrames", "receivedBytes", "sentBytes"):
            total[key] += channel.get(key, 0)
        for key, value in inspection.get("operations", {}).items():
            total["operations"][key] = total["operations"].get(key, 0) + value
        for direction, kinds in channel.get("byKind", {}).items():
            for kind, counts in kinds.items():
                target = total["byKind"][direction].setdefault(kind, {"frames": 0, "bytes": 0})
                for key in ("frames", "bytes"):
                    target[key] += counts[key]
        for target, source in (("peakClientBufferedBytes", "peakBufferedBytes"),
                               ("peakClientBufferedControlBytes", "peakBufferedControlBytes"),
                               ("peakSubscriptionQueueFrames", "peakQueueFrames"),
                               ("peakRetainedHandles", "retainedHandles")):
            total[target] = max(total[target], inspection.get(source, 0))

    def inspect(self):
        """Cumulative local measurements, including retired channels; no native data.

        Queue peaks are maxima per Client/subscription, not simultaneous fleet
        peaks. Uninstrumented adapters are counted explicitly, never as zero IO.
        """
        total = copy.deepcopy(self._totals)
        for client in self._clients.values():
            self._merge_metrics(total, client)
        return {"format": "mesh-plus.reader-metrics.v1", "domain": self.domain,
                "byteScope": "completed-json-lines", "activeConnections": len(self._clients),
                "partial": total["uninstrumentedConnections"] > 0 or self._counts["connectionFailures"] > 0,
                **self._counts, **total}

    async def _connect(self, endpoint):
        self._counts["connectionAttempts"] += 1
        try:
            client = await endpoint.connect()
        except BaseException:
            self._counts["connectionFailures"] += 1
            raise
        self._clients[id(client)] = client
        self._counts["connectionsOpened"] += 1
        self._counts["peakConnections"] = max(self._counts["peakConnections"], len(self._clients))
        return client

    async def _close(self, client):
        cleanup = asyncio.create_task(client.close())
        try:
            await finish_owned(cleanup)
        except BaseException:
            if cleanup.cancelled() or (cleanup.done() and cleanup.exception() is not None):
                self._counts["cleanupFailures"] += 1
            raise
        finally:
            self._merge_metrics(self._totals, client)
            self._clients.pop(id(client), None)
            self._counts["connectionsClosed"] += 1

    async def execute(self, request):
        iterator = self._execute(request, admitted=False)
        try:
            async for frame in iterator:
                yield frame
        finally:
            await iterator.aclose()

    async def execute_admitted(self, request):
        """Opt-in watch handoff; snapshots retain the strict ordinary JSON API."""
        iterator = self._execute(request, admitted=True)
        try:
            async for frame in iterator:
                yield frame
        finally:
            await iterator.aclose()

    async def _execute(self, request, *, admitted):
        """Validated Read 1 request -> one snapshot or replacement watch stream."""
        from .protocol import validate_read_request
        request_id = None
        try:
            supplied_id = request.get("requestId") if isinstance(request, dict) else None
            if isinstance(supplied_id, str) and re.fullmatch(r"[0-9a-f]{32,64}", supplied_id):
                request_id = supplied_id
            validate_read_request(request, self.profile.descriptor.profile_id)
            request_id = request["requestId"]
            selection = request["selection"]
            # Resolve all selections before opening any source, even for watch.
            self.selection(selection["mode"], selection["hostIds"])
            if request["operation"] == "snapshot":
                yield await self.snapshot(mode=selection["mode"], hosts=selection["hostIds"], request_id=request_id)
            else:
                watch = self.watch_admitted if admitted else self.watch
                iterator = watch(mode=selection["mode"], hosts=selection["hostIds"], request_id=request_id)
                try:
                    async for frame in iterator:
                        yield frame
                finally:
                    await iterator.aclose()
        except Exception as error:
            yield {"meshProtocol": 1, "requestId": request_id,
                   "error": {"code": outcome_code(error), "message": "Mesh request failed"}}

    def selection(self, mode="fleet", hosts=()):
        check(mode in {"local", "fleet", "hosts"} and (mode == "hosts") == bool(hosts), "selection_shape")
        if mode == "hosts":
            check(len(hosts) == len(set(hosts)), "duplicate_host")
            known = {endpoint.host: endpoint for endpoint in self.endpoints}
            check(all(host in known for host in hosts), "unknown_host")
            return tuple(known[host] for host in hosts)
        selected = tuple(endpoint for endpoint in self.endpoints if mode == "fleet" or endpoint.local)
        check(bool(selected), "empty_scope")
        return selected

    def unavailable(self, endpoint, code="source_unavailable", epoch=1):
        return {"hostId": endpoint.host, "local": endpoint.local,
                "delivery": {"path": "ipc" if endpoint.local else "ssh", "status": "unavailable", "epoch": epoch,
                             "routeToken": endpoint.route_token, "error": {"code": code, "message": "Source delivery unavailable"},
                             "proof": None}, "viewState": "unavailable", "owner": None, "receipts": []}

    def _codec(self, client, endpoint):
        codec = endpoint.codec
        if codec is None:
            codec = legacy_codec(self.domain, self.profile, endpoint.host, client.codec)
        binding = self._bindings.get(id(endpoint), (endpoint.host, codec.source, self.profile.descriptor.profile_id))
        check_binding(codec, *binding)
        guard = getattr(client, "guard", None)
        if guard is not None:
            check(guard.authenticated_host == codec.host and guard.hello["sourceId"] == codec.source and
                  guard.hello["profile"] == codec.profile_id, "endpoint_client_binding")
        return codec

    async def read_host(self, client, endpoint, epoch=1, *, _state=None):
        codec = self._codec(client, endpoint)
        proof = None
        if endpoint.local:
            reply = await client.request()
            check(reply["clock"] == clock_domain(), "local_clock_scope")
        else:
            nonce = secrets.token_hex(16)
            sent = boottime_ms()
            reply = await client.request("proof", {"nonce": nonce}, timeout_ms=2000)
            received = boottime_ms()
            check(reply["kind"] == "proof" and reply["nonce"] == nonce and reply["hostId"] == endpoint.host,
                  "proof_request_binding")
            remote_expiry(sent, received, 0)
            proof = {"nonce": nonce, "bridgeId": reply["bridgeId"], "bridgeClock": reply["clock"],
                     "bridgeEncodedAtMs": reply["encodedAtMs"], "sentAtMs": sent, "receivedAtMs": received,
                     "marginMs": 100, "payloadDigest": reply["ownerDigest"]}
        state = validate_bridge(self.profile, codec, reply)
        now = boottime_ms()
        receipts = []
        for original in state.receipts:
            receipt = dict(original)
            original_expiry = receipt.pop("expiry")
            remaining = max(0, original_expiry - (now if endpoint.local else reply["encodedAtMs"])) if receipt["health"] in {"current", "partial"} else 0
            expiry = original_expiry if endpoint.local else remote_expiry(sent, received, remaining)
            if remaining == 0 or expiry <= now:
                if receipt["health"] in {"current", "partial"}:
                    receipt["health"] = "stale"
                expiry, remaining = None, 0
            receipts.append({**receipt, "remainingMs": remaining, "expiresAtMs": expiry})
        current = any(r["health"] in {"current", "partial"} for r in receipts)
        result = {"hostId": endpoint.host, "local": endpoint.local,
                  "delivery": {"path": "ipc" if endpoint.local else "ssh", "status": "ready", "epoch": epoch,
                               "routeToken": getattr(client, "route_token", endpoint.route_token), "error": None, "proof": proof},
                  "viewState": "warming" if state.owner["metadata"] is None else "current" if current else "historical",
                  "owner": state.owner, "receipts": receipts}
        if _state is not None:
            _state.append(state)
        return result, list(state.records)

    def compose(self, selected, outcomes, request_id, operation="snapshot", *, state=None, kind="view"):
        return self._compose(selected, outcomes, request_id, operation, state=state, kind=kind, admitted=False)

    def compose_admitted(self, selected, outcomes, request_id, operation="watch", *, state=None, kind="view"):
        """Compose and fully admit once into a process-local owned handoff."""
        return self._compose(selected, outcomes, request_id, operation, state=state, kind=kind, admitted=True)

    def _compose(self, selected, outcomes, request_id, operation, *, state, kind, admitted):
        now = boottime_ms()
        state = PublicationState() if state is None else state
        hosts, sessions = [], []
        for endpoint in selected:
            host, rows = copy.deepcopy(outcomes[endpoint.host])
            for receipt in host["receipts"]:
                if receipt["expiresAtMs"] is not None and receipt["expiresAtMs"] <= now:
                    receipt.update(health="stale", expiresAtMs=None, remainingMs=0)
            if host["viewState"] == "current" and not any(r["health"] in {"current", "partial"} for r in host["receipts"]):
                host["viewState"] = "historical"
            hosts.append(host)
            sessions.extend(rows)
        states = [host["delivery"]["status"] for host in hosts]
        status = "complete" if all(s == "ready" for s in states) else "partial" if "ready" in states else "pending" if "connecting" in states else "unavailable"
        fingerprint = digest({"hosts": hosts, "sessions": sessions, "kind": kind,
                              "scope": [e.host for e in selected], "catalogRevision": self.catalog_revision})
        sequence = state.sequence + 1
        revision = state.revision + (fingerprint != state.fingerprint)
        response = {"protocol": self.profile.descriptor.profile_id, "schemaVersion": 1,
                    "mesh": {"meshProtocol": 1, "requestId": request_id, "operation": operation, "access": "cached",
                             "scope": {"hostIds": [e.host for e in selected]},
                             "catalog": {"state": "ready" if self.catalog_revision else "local_only",
                                         "revision": self.catalog_revision, "localHostId": self.local_host},
                             "reader": {"id": self.id, "clock": clock_domain(), "encodedAtMs": now,
                                        "sequence": sequence, "revision": revision},
                             "kind": kind, "status": status, "hosts": hosts, "extensions": {}}, "sessions": sessions}
        _, native = _validated_response(response, self.profile)
        result = AdmittedResponse._owned(response, native, self.profile) if admitted else response
        state.sequence, state.revision, state.fingerprint = sequence, revision, fingerprint
        return result

    async def snapshot(self, *, mode="fleet", hosts=(), timeout_ms=15000, request_id=None):
        selected = self.selection(mode, hosts)
        check(type(timeout_ms) is int and 1 <= timeout_ms <= 15000, "snapshot_budget")
        request_id = secrets.token_hex(16) if request_id is None else request_id
        check(isinstance(request_id, str) and len(request_id) in range(32, 65) and
              all(c in "0123456789abcdef" for c in request_id), "request_id")
        deadline = boottime_ms() + timeout_ms

        async def one(endpoint):
            client = None
            try:
                async def dispatch():
                    nonlocal client
                    async with self.setup_slots:
                        client = await self._connect(endpoint)
                        return await self.read_host(client, endpoint)
                return await within_deadline(dispatch(), deadline)
            except Exception as error:
                code = outcome_code(error)
                outcome = self.unavailable(endpoint, code)
                outcome["delivery"]["routeToken"] = getattr(error, "route_token", endpoint.route_token)
                return outcome, []
            finally:
                if client:
                    await self._close(client)

        tasks = [asyncio.create_task(one(endpoint)) for endpoint in selected]
        try:
            values = await asyncio.gather(*tasks)
        except BaseException:
            # gather may report one cancelled child before sibling finally
            # blocks retire their clients. The snapshot owns all of them.
            for task in tasks:
                if not task.done():
                    task.cancel()
            retirement = asyncio.gather(*tasks, return_exceptions=True)
            await finish_owned(retirement)
            raise
        return self.compose(selected, {e.host: value for e, value in zip(selected, values)}, request_id)

    async def watch(self, *, mode="fleet", hosts=(), proof_interval=None, request_id=None, catalog_interval=5):
        iterator = self._watch(mode=mode, hosts=hosts, proof_interval=proof_interval,
                               request_id=request_id, catalog_interval=catalog_interval, admitted=False)
        try:
            async for frame in iterator:
                yield frame
        finally:
            await iterator.aclose()

    async def watch_admitted(self, *, mode="fleet", hosts=(), proof_interval=None, request_id=None, catalog_interval=5):
        """Owned full views; controls and terminal errors remain ordinary JSON."""
        iterator = self._watch(mode=mode, hosts=hosts, proof_interval=proof_interval,
                               request_id=request_id, catalog_interval=catalog_interval, admitted=True)
        try:
            async for frame in iterator:
                yield frame
        finally:
            await iterator.aclose()

    async def _watch(self, *, mode, hosts, proof_interval, request_id, catalog_interval, admitted):
        compose = self.compose_admitted if admitted else self.compose
        selected = self.selection(mode, hosts)
        request_id = secrets.token_hex(16) if request_id is None else request_id
        check(isinstance(request_id, str) and len(request_id) in range(32, 65) and
              all(c in "0123456789abcdef" for c in request_id), "request_id")
        check(.01 <= catalog_interval <= 5, "catalog_interval")
        def terminal(code):
            return {"meshProtocol": 1, "requestId": request_id,
                    "error": {"code": code, "message": "Catalog authority unavailable or changed; resubscribe"}}
        if self.catalog_revision is not None and not callable(self.catalog_check):
            yield terminal("catalog_monitor_required")
            return
        interval = proof_interval or (3 if self.domain == "tmux" else 10)
        check(.1 <= interval <= 60, "proof_interval")
        outcomes = {e.host: (self.unavailable(e), []) for e in selected}
        for host, _rows in outcomes.values():
            host["delivery"].update(status="connecting", error=None)
        changed = asyncio.Event()
        fatal = None
        resync = False
        rotation_barriers = {}

        async def monitor_catalog():
            nonlocal fatal
            while True:
                started = boottime_ms()
                self._counts["catalogChecks"] += 1
                try:
                    revision = await within_deadline(self.catalog_check(), started + 5000)
                    check(revision == self.catalog_revision, "scope_changed")
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    fatal = "scope_changed" if getattr(error, "code", None) == "scope_changed" else "catalog_unavailable"
                    changed.set()
                    return
                finally:
                    self._counts["catalogCheckMs"] += max(0, boottime_ms() - started)
                await asyncio.sleep(max(0, catalog_interval - (boottime_ms() - started) / 1000))

        async def host_loop(endpoint):
            nonlocal resync
            epoch = 0
            retry = .25
            previous_publisher = None
            while True:
                client, sub, next_frame = None, None, None
                rotation_barrier = None
                epoch += 1
                try:
                    async def setup():
                        nonlocal client, sub
                        async with self.setup_slots:
                            client = await self._connect(endpoint)
                            self._codec(client, endpoint)
                            sub = await client.subscribe()
                    await within_deadline(setup(), boottime_ms() + 15000)
                    # Baseline is a candidate: accept positives only through a cached read/proof.
                    while True:
                        if callable(getattr(client, "rotation_due", None)) and client.rotation_due():
                            raise DeliveryError("channel_rotation_required")
                        admitted = []
                        replacement = await self.read_host(client, endpoint, epoch, _state=admitted)
                        publisher = admitted[0].publisher
                        resync = resync or (previous_publisher is not None and previous_publisher != publisher)
                        previous_publisher = publisher
                        outcomes[endpoint.host] = replacement
                        resync = resync or epoch > 1
                        retry = .25
                        changed.set()
                        deadline = boottime_ms() + int(interval * 1000)
                        while boottime_ms() < deadline:
                            if next_frame is None:
                                next_frame = asyncio.create_task(anext(sub))
                            if await _wait_until(next_frame, deadline):
                                frame = next_frame.result()
                                next_frame = None
                                if frame["kind"] == "control" and frame["control"] == "heartbeat":
                                    continue
                                if frame["kind"] == "control":
                                    resync = True
                                    outcomes[endpoint.host] = self.unavailable(endpoint, "source_gap", epoch), []
                                    changed.set()
                                    # Let downstream revoke before any subsequent proof repairs the gap.
                                    await asyncio.sleep(0)
                                break
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    code = outcome_code(error)
                    if code == "channel_rotation_required":
                        self._counts["rotations"] += 1
                        rotation_barrier = asyncio.Event()
                        rotation_barriers[endpoint.host] = rotation_barrier
                    outcomes[endpoint.host] = self.unavailable(endpoint, code, epoch), []
                    resync = True
                    changed.set()
                finally:
                    try:
                        if next_frame:
                            next_frame.cancel()
                            await asyncio.gather(next_frame, return_exceptions=True)
                    finally:
                        if client:
                            await self._close(client)
                if rotation_barrier is not None:
                    # A consumer must receive revocation before fresh proof can
                    # overwrite it, even while it is paused between frames.
                    await rotation_barrier.wait()
                    continue
                await asyncio.sleep(retry)
                retry = min(30, retry * 2)

        tasks = [asyncio.create_task(host_loop(endpoint)) for endpoint in selected]
        if self.catalog_revision is not None:
            tasks.append(asyncio.create_task(monitor_catalog()))
        try:
            state = PublicationState()
            yield compose(selected, outcomes, request_id, "watch", state=state)
            while True:
                expires = [r["expiresAtMs"] for host, _rows in outcomes.values() for r in host["receipts"]
                           if r["expiresAtMs"] is not None and r["expiresAtMs"] > boottime_ms()]
                timeout = max(.001, (min(expires) - boottime_ms()) / 1000) if expires else None
                expired = False
                try:
                    await asyncio.wait_for(changed.wait(), timeout)
                except TimeoutError:
                    expired = True
                changed.clear()
                if fatal:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    yield terminal(fatal)
                    return
                if expired:
                    for host, _rows in outcomes.values():
                        for receipt in host["receipts"]:
                            if receipt["expiresAtMs"] is not None and receipt["expiresAtMs"] <= boottime_ms():
                                receipt.update(health="stale", remainingMs=0, expiresAtMs=None)
                response = compose(selected, outcomes, request_id, "watch", state=state,
                                        kind="resync" if resync else "view")
                resync = False
                for barrier in rotation_barriers.values():
                    barrier.set()
                rotation_barriers.clear()
                yield response
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
