"""Disposable design probe against current runtime; not a replacement SDK."""
import asyncio
import hashlib
import importlib.abc
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

class RejectObserverImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"agent_observer", "tmux_observer"}:
            raise ImportError("observer imports forbidden in this generic probe")

sys.meta_path.insert(0, RejectObserverImports())
from mesh_plus.bridge import Bridge, Publication
from mesh_plus.client import Client
from mesh_plus.configured_read import configured_reader
from mesh_plus.reader import Endpoint, Reader
from mesh_plus.transport import IPCServer, connect_ipc

def validate(value):
    assert type(value) is dict and set(value) == {"sample"}
    assert type(value["sample"]) is int
    return value

class Publisher:
    host = "fixture"
    source = "fixture"
    profile = "agent-observer.mesh-candidate.v1"
    capabilities = ("snapshot", "proof", "subscribe")
    validate = staticmethod(validate)
    async def snapshot(self, parameters):
        assert parameters == {}
        return {"sample": 1}
    async def proof(self, parameters):
        assert set(parameters) == {"nonce"}
        return {"sample": 2}
    async def watch(self):
        try:
            yield Publication({"sample": 3}, "fixture_epoch", {"revision": 1})
            await asyncio.Event().wait()
        finally:
            self.watch_closed = True

async def main():
    errors = []
    asyncio.get_running_loop().set_exception_handler(lambda loop, context: errors.append(str(context.get("message"))))
    pub = Publisher();pub.watch_closed = False
    with tempfile.TemporaryDirectory(prefix="mesh-sdk-boundary-") as directory:
        server = await IPCServer(Path(directory)/"read.sock", Bridge(pub).serve).start()
        client = await Client.connect(await connect_ipc(server.path), host=pub.host, source=pub.source,
                                      profile=pub.profile, codec=validate, required=pub.capabilities)
        try:
            assert await client.request() == {"sample": 1}
            assert await client.request("proof", {"nonce": "a"*32}) == {"sample": 2}
            subscription = await client.subscribe()
            pushed = await asyncio.wait_for(anext(subscription), 2)
            assert pushed["payload"] == {"sample": 3}
            await subscription.close()
        finally:
            await client.close();await server.close()
    await asyncio.sleep(.05)
    assert pub.watch_closed and not errors, errors
    endpoint = Endpoint("fixture", True, None, AsyncMock())
    reader = Reader("agent", [endpoint], local_host="fixture")
    dummy = SimpleNamespace(codec=validate, request=AsyncMock())
    try:
        await reader.read_host(dummy, endpoint)
    except AttributeError as error:
        assert "__self__" in str(error)
    else:
        raise AssertionError("expected current Reader codec-introspection rejection")
    dummy.request.assert_not_awaited()
    try:
        await configured_reader("agent", source="fixture", socket="/owned/read.sock", scope="local", local_host="fixture", profile=object())
    except TypeError as error:
        assert "profile" in str(error)
    else:
        raise AssertionError("expected current configured-reader injection rejection")
    return {"state":"passed", "scope":"current-runtime generic Delivery and negative SDK seam probes; no Observer acceptance", "observerImportsBlocked":True,
            "genericRequestProofSubscribe":True,"genericPublisherClosed":True,"loopDiagnostics":errors,
            "readerCallableCodecRejectedBeforeRequest":True,"configuredProfileInjectionUnavailable":True,
            "syntheticPayloadIsNotFrozenNativeProfileAcceptance":True,"nativeCollection":False,"managedDeployment":False}

if __name__ == "__main__":
    report=asyncio.run(main());report["probeSha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
