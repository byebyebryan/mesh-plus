"""Ordered request handles: host atomicity without a cross-host transaction."""

import secrets
from dataclasses import dataclass

from ..protocol import ProtocolError, check
from .budget import AllocationLedger
from .canonical import Atom, thaw


@dataclass(frozen=True, slots=True)
class UnavailableHost:
    host: str
    reason: str


@dataclass(frozen=True, slots=True)
class _HostPin:
    host: str
    instance: str
    tag: object
    reason: str


class AggregateCommit:
    """An exact request/catalog/order and a bounded set of confirmed host tags.

    Pins contain no native graph. Each query rechecks the live request, channel
    and source cache. A later host never silently replaces a captured tag.
    """

    __slots__ = ("_owner", "_permit", "_pins")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable aggregate commit")
        object.__setattr__(self, name, value)

    def __init__(self, owner, permit, pins):
        self._owner, self._permit, self._pins = owner, permit, pins

    @property
    def binding(self):
        return thaw(self._owner.binding.value)

    def host(self, host):
        for pin in self._pins:
            if pin.host == host:
                return self._owner.resolve(self._permit, pin)
        raise KeyError(host)

    def hosts(self):
        result = []
        for pin in self._pins:
            value = self._owner.resolve(self._permit, pin)
            result.append({"host": pin.host, "status": "unavailable" if type(value) is UnavailableHost else "confirmed",
                           "tag": None if type(value) is UnavailableHost else pin.tag.wire(),
                           "reason": value.reason if type(value) is UnavailableHost else None})
        return tuple(result)


@dataclass(slots=True)
class _HostSlot:
    instance: str
    cache: object = None
    reason: str = "unconfirmed"


class AggregateState:
    """Reader-owned state; only cache-confirmed views enter an aggregate.

    Network acquisition and I/O cleanup belong to the Reader. This object owns
    its per-host caches, lifecycle and bounded immutable request metadata.
    """

    def __init__(self, *, source, profile, hosts, catalog_revision, routes, reader_epoch, request_id, ledger=None):
        check(type(hosts) is tuple and 0 < len(hosts) <= 16 and len(set(hosts)) == len(hosts) and
              all(type(host) is str and 0 < len(host) <= 256 for host in hosts), "sync_host_selection")
        check(type(routes) is tuple and len(routes) == len(hosts) and
              all(route is None or type(route) is str and 0 < len(route) <= 256 for route in routes),
              "sync_route_selection")
        check(all(type(value) is str and 0 < len(value) <= 128 for value in (reader_epoch, request_id)),
              "sync_request_epoch")
        check(catalog_revision is None or type(catalog_revision) is str and len(catalog_revision) <= 256,
              "sync_catalog_revision")
        self.profile, self.source = profile, source
        self.ledger = AllocationLedger() if ledger is None else ledger
        self.binding = Atom.own({"source": source, "descriptor": profile.descriptor.wire(),
                                 "hosts": list(hosts), "catalogRevision": catalog_revision, "routes": list(routes),
                                 "readerEpoch": reader_epoch, "requestId": request_id})
        check(len(self.binding.encoded) <= 8192, "sync_request_binding_capacity")
        self._permit = secrets.token_hex(16)
        self._slots = {host: _HostSlot(secrets.token_hex(16)) for host in hosts}
        self._closed_reason = "request_closed"
        self.ledger.retain(self.binding)

    def attach(self, host, cache):
        check(self._permit is not None and host in self._slots, "sync_request_retired")
        check(cache._binding.value["host"] == host and cache._binding.value["source"] == self.source and
              cache.profile is self.profile and cache.ledger is self.ledger, "sync_host_binding")
        request = cache._request.value
        selection = self.binding.value
        index = list(self._slots).index(host)
        check(all(request.get(name) == selection[name] for name in ("readerEpoch", "requestId", "catalogRevision", "hosts")) and
              request.get("route") == selection["routes"][index], "sync_aggregate_request_binding")
        check(all(type(request.get(name)) is str and len(request[name]) == 32 for name in ("channelEpoch", "bridgeId")),
              "sync_channel_epoch")
        slot = self._slots[host]
        if slot.cache is not None and slot.cache is not cache:
            slot.cache.close()
        slot.cache, slot.instance, slot.reason = cache, secrets.token_hex(16), "unconfirmed"

    def revoke_host(self, host, reason):
        check(type(reason) is str and 0 < len(reason) <= 256, "sync_revoke_reason")
        slot = self._slots[host]
        slot.reason = reason
        if slot.cache is not None:
            slot.cache.revoke(reason)

    def capture(self):
        check(self._permit is not None, "sync_request_retired")
        pins = []
        for host, slot in self._slots.items():
            try:
                view = None if slot.cache is None else slot.cache.acquire()
                tag = None if view is None else view.tag
            except ProtocolError:
                tag = None
            pins.append(_HostPin(host, slot.instance, tag, slot.reason))
        return AggregateCommit(self, self._permit, tuple(pins))

    def resolve(self, permit, pin):
        if self._permit is None or permit != self._permit:
            return UnavailableHost(pin.host, self._closed_reason)
        slot = self._slots[pin.host]
        if slot.instance != pin.instance:
            return UnavailableHost(pin.host, "channel_replaced")
        if pin.tag is None or slot.cache is None:
            return UnavailableHost(pin.host, pin.reason)
        try:
            view = slot.cache.acquire()
            if view.tag == pin.tag:
                return view
        except ProtocolError:
            return UnavailableHost(pin.host, slot.reason if slot.reason != "unconfirmed" else slot.cache.reason)
        return UnavailableHost(pin.host, "tag_superseded")

    def close(self, reason="request_closed"):
        if self._permit is None:
            return
        check(type(reason) is str and 0 < len(reason) <= 256, "sync_revoke_reason")
        self._permit, self._closed_reason = None, reason
        for slot in self._slots.values():
            if slot.cache is not None:
                slot.cache.close()
                slot.cache = None
        self.ledger.release(self.binding)
