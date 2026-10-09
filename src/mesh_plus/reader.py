"""Fleet composition over independently bound delivery clients."""

import asyncio
import copy
import secrets
import uuid
from dataclasses import dataclass

from .observer import clock_domain
from .protocol import check
from .transport import boottime_ms
from .view import remote_expiry, validate_response


@dataclass(frozen=True)
class Endpoint:
    host: str
    local: bool
    route_token: str | None
    connect: object


class Reader:
    def __init__(self, domain, endpoints, *, local_host, catalog_revision=None):
        check(domain in {"tmux", "agent"}, "observer_domain")
        self.domain, self.local_host, self.catalog_revision = domain, local_host, catalog_revision
        self.endpoints = tuple(endpoints)
        check(len({endpoint.host for endpoint in self.endpoints}) == len(self.endpoints) and
              1 <= len(self.endpoints) <= 16, "endpoint_scope")
        check(all(endpoint.local == (endpoint.host == local_host) for endpoint in self.endpoints), "endpoint_local_binding")
        check(all((endpoint.route_token is None) == endpoint.local for endpoint in self.endpoints), "endpoint_route_binding")
        check(catalog_revision is not None or [e.host for e in self.endpoints] == [local_host], "catalog_required")
        self.id = str(uuid.uuid4())
        self.sequence = 0

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

    async def read_host(self, client, endpoint, epoch=1):
        codec = client.codec.__self__
        check(codec.domain == self.domain and codec.host == endpoint.host, "endpoint_codec_binding")
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
        frame = reply["ownerFrame"]
        now = boottime_ms()
        receipts = []
        for receipt in codec.receipts(frame):
            original_expiry = receipt.pop("expiry")
            remaining = max(0, original_expiry - (now if endpoint.local else reply["encodedAtMs"])) if receipt["health"] in {"current", "partial"} else 0
            expiry = original_expiry if endpoint.local else remote_expiry(sent, received, remaining)
            if remaining == 0 or expiry <= now:
                if receipt["health"] in {"current", "partial"}:
                    receipt["health"] = "stale"
                expiry, remaining = None, 0
            receipts.append({**receipt, "remainingMs": remaining, "expiresAtMs": expiry})
        snapshot = frame["snapshot"]
        metadata = None if snapshot is None else {key: value for key, value in snapshot.items() if key != "sessions"}
        service = {key: value for key, value in frame.items() if key != "snapshot"}
        current = any(r["health"] in {"current", "partial"} for r in receipts)
        result = {"hostId": endpoint.host, "local": endpoint.local,
                  "delivery": {"path": "ipc" if endpoint.local else "ssh", "status": "ready", "epoch": epoch,
                               "routeToken": endpoint.route_token, "error": None, "proof": proof},
                  "viewState": "warming" if snapshot is None else "current" if current else "historical",
                  "owner": {"protocol": "tmux-observer.observation.v1" if self.domain == "tmux" else "agent-observer.snapshot",
                            "version": 1 if self.domain == "tmux" else 4, "metadata": metadata, "service": service},
                  "receipts": receipts}
        return result, [] if snapshot is None else snapshot["sessions"]

    def compose(self, selected, outcomes, request_id, operation="snapshot"):
        now = boottime_ms()
        self.sequence += 1
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
        status = "complete" if all(s == "ready" for s in states) else "partial" if "ready" in states else "unavailable"
        response = {"protocol": self.domain + "-observer.mesh-candidate.v1", "schemaVersion": 1,
                    "mesh": {"meshProtocol": 1, "requestId": request_id, "operation": operation, "access": "cached",
                             "scope": {"hostIds": [e.host for e in selected]},
                             "catalog": {"state": "ready" if self.catalog_revision else "local_only",
                                         "revision": self.catalog_revision, "localHostId": self.local_host},
                             "reader": {"id": self.id, "clock": clock_domain(), "encodedAtMs": now,
                                        "sequence": self.sequence, "revision": self.sequence},
                             "kind": "view", "status": status, "hosts": hosts, "extensions": {}}, "sessions": sessions}
        return validate_response(response)

    async def snapshot(self, *, mode="fleet", hosts=()):
        selected = self.selection(mode, hosts)

        async def one(endpoint):
            client = None
            try:
                client = await endpoint.connect()
                return await self.read_host(client, endpoint)
            except Exception:
                return self.unavailable(endpoint), []
            finally:
                if client:
                    await client.close()

        values = await asyncio.gather(*(one(endpoint) for endpoint in selected))
        return self.compose(selected, {e.host: value for e, value in zip(selected, values)}, secrets.token_hex(16))

    async def watch(self, *, mode="fleet", hosts=(), proof_interval=None):
        selected = self.selection(mode, hosts)
        request_id = secrets.token_hex(16)
        interval = proof_interval or (3 if self.domain == "tmux" else 10)
        check(.1 <= interval <= 60, "proof_interval")
        outcomes = {e.host: (self.unavailable(e), []) for e in selected}
        changed = asyncio.Event()

        async def host_loop(endpoint):
            epoch = 0
            while True:
                client, sub, next_frame = None, None, None
                epoch += 1
                try:
                    client = await endpoint.connect()
                    sub = await client.subscribe()
                    # Baseline is a candidate: accept positives only through a cached read/proof.
                    while True:
                        outcomes[endpoint.host] = await self.read_host(client, endpoint, epoch)
                        changed.set()
                        deadline = boottime_ms() + int(interval * 1000)
                        while boottime_ms() < deadline:
                            if next_frame is None:
                                next_frame = asyncio.create_task(anext(sub))
                            done, _ = await asyncio.wait({next_frame}, timeout=min(.1, max(0, (deadline - boottime_ms()) / 1000)))
                            if done:
                                frame = next_frame.result()
                                next_frame = None
                                if frame["kind"] == "control" and frame["control"] == "heartbeat":
                                    continue
                                if frame["kind"] == "control":
                                    outcomes[endpoint.host] = self.unavailable(endpoint, "source_gap", epoch), []
                                    changed.set()
                                    # Let downstream revoke before any subsequent proof repairs the gap.
                                    await asyncio.sleep(0)
                                break
                except asyncio.CancelledError:
                    raise
                except Exception:
                    outcomes[endpoint.host] = self.unavailable(endpoint, epoch=epoch), []
                    changed.set()
                finally:
                    if next_frame:
                        next_frame.cancel()
                        await asyncio.gather(next_frame, return_exceptions=True)
                    if client:
                        await client.close()
                await asyncio.sleep(.25)

        tasks = [asyncio.create_task(host_loop(endpoint)) for endpoint in selected]
        try:
            yield self.compose(selected, outcomes, request_id, "watch")
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
                if expired:
                    for host, _rows in outcomes.values():
                        for receipt in host["receipts"]:
                            if receipt["expiresAtMs"] is not None and receipt["expiresAtMs"] <= boottime_ms():
                                receipt.update(health="stale", remainingMs=0, expiresAtMs=None)
                yield self.compose(selected, outcomes, request_id, "watch")
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
