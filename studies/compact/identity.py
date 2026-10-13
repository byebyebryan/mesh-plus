"""Actual disposable Tmux cached-proof identity; no field-exclusion fast path."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

from tmux_observer.mesh_profile import TmuxMeshProfile
from tmux_observer.mesh_publisher import make_publisher

from mesh_plus.evidence import digest
from mesh_plus.testing.sample import Publisher
from mesh_plus.transport import boottime_ms


def differences(left, right, path=""):
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            name = path + "/" + key
            result.extend([name] if key not in left or key not in right else differences(left[key], right[key], name))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [path + "/length"]
        return [name for index, (a, b) in enumerate(zip(left, right, strict=True)) for name in differences(a, b, path + "/" + str(index))]
    return [] if left == right else [path]


def compare(label, retained, proof, codec):
    fresh = proof["ownerFrame"]
    assert proof["ownerDigest"] == digest(fresh)
    a, b = codec.inspect_native(retained), codec.inspect_native(fresh)
    return {"case": label, "rawDigestMatch": digest(retained) == proof["ownerDigest"],
            "changedPaths": differences(retained, fresh), "sameRecords": a.records == b.records,
            "sameOriginalReceipts": a.receipts == b.receipts, "samePublisher": a.publisher == b.publisher,
            "sameClock": a.clock == b.clock, "retainedRows": len(a.records), "freshRows": len(b.records)}


async def command(env, *args):
    child = await asyncio.create_subprocess_exec(*args, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(child.communicate(), 5)
    if child.returncode:
        raise ValueError("owned_command_failed:" + stderr.decode())
    return stdout


async def retire(child):
    if child.returncode is None:
        child.terminate()
        try:
            await asyncio.wait_for(child.wait(), 5)
        except TimeoutError:
            child.kill()
            await child.wait()


async def run(args):
    profile = TmuxMeshProfile()
    codec = profile.bind("beta", "controlled")
    report = {"status": "passed", "nativeInput": "tmux-observer 0.6.0a7 pinned wheel",
              "scope": "disposable actual native default-server namespace and owner; cached make_publisher proof after fresh nonce",
              "pairs": [], "pureOwnerCases": [], "excluded": ["active Agent", "ordinary tmux server", "compact runtime", "field exclusions"]}
    with tempfile.TemporaryDirectory(prefix="mesh-identity-") as name:
        root = Path(name)
        root.chmod(0o700)
        env = {**os.environ, "TMUX_TMPDIR": str(root)}
        env.pop("TMUX", None)
        env.pop("TMUX_PANE", None)
        owner = None
        source = make_publisher("beta", "controlled", root / "owner.sock")

        async def start():
            return await asyncio.create_subprocess_exec(sys.executable, "-I", "-B", "-m", "tmux_observer", "owner",
                "--host-id", "beta", "--socket", str(root / "owner.sock"), env=env,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)

        async def frame_until(predicate):
            async with asyncio.timeout(8):
                while True:
                    if owner.returncode is not None:
                        raise ValueError("owner_exited:" + (await owner.stderr.read()).decode())
                    try:
                        value = (await source.snapshot({}))["ownerFrame"]
                    except FileNotFoundError:
                        await asyncio.sleep(.02)
                        continue
                    if predicate(value):
                        return value
                    await asyncio.sleep(.05)

        async def proof():
            nonce = secrets.token_hex(16)
            value = await source.proof({"nonce": nonce})
            assert value["nonce"] == nonce
            return value

        try:
            await command(env, "tmux", "-L", "default", "-f", "/dev/null", "new-session", "-d", "-s", "identity-fixture", "sleep 180")
            owner = await start()
            initial = await frame_until(lambda value: value["snapshot"] is not None and len(value["snapshot"]["sessions"]) == 1)
            for _ in range(20):
                retained = (await source.snapshot({}))["ownerFrame"]
                report["pairs"].append(compare("unchanged_cached_read", retained, await proof(), codec))
                await asyncio.sleep(.02)
            retained = initial
            await frame_until(lambda value: value["receipt"]["accepted"] > retained["receipt"]["accepted"])
            report["pairs"].append(compare("new_accepted_evidence_same_records", retained, await proof(), codec))
            watch = source.native.watch()
            try:
                publication = await asyncio.wait_for(anext(watch), 4)
                report["pairs"].append(compare("watch_to_status_proof", publication.frame, await proof(), codec))
                retained_watch = publication.frame
                try:
                    publication = await asyncio.wait_for(anext(watch), 5)
                    retained_watch = publication.frame
                    report["idleWatch"] = "new native publication received"
                except TimeoutError:
                    report["idleWatch"] = "no replacement within five seconds; native source filters idle heartbeat frames"
                report["pairs"].append(compare("idle_native_watch_to_proof", retained_watch, await proof(), codec))
            finally:
                await watch.aclose()
            retained = (await source.snapshot({}))["ownerFrame"]
            await command(env, "tmux", "-L", "default", "rename-session", "-t", "identity-fixture", "identity-changed")
            await frame_until(lambda value: value["snapshot"] and value["snapshot"]["sessions"][0]["name"] == "identity-changed")
            report["pairs"].append(compare("changed_native_records", retained, await proof(), codec))
            await command(env, "tmux", "-L", "default", "kill-session", "-t", "identity-changed")
            empty = await frame_until(lambda value: value["snapshot"] is not None and not value["snapshot"]["sessions"])
            report["pairs"].append(compare("ready_empty", empty, await proof(), codec))
            retained = (await source.snapshot({}))["ownerFrame"]
            await retire(owner)
            before = source.sequence
            try:
                await proof()
            except (OSError, ValueError, TimeoutError) as error:
                report["sourceLoss"] = {"status": "rejected_fresh_proof", "exceptionType": type(error).__name__,
                                        "wrapperSequenceUnchanged": source.sequence == before}
            else:
                raise AssertionError("stopped_owner_proved")
            owner = await start()
            await frame_until(lambda value: value["snapshot"] is not None)
            report["pairs"].append(compare("owner_restart", retained, await proof(), codec))
        finally:
            if owner is not None:
                await retire(owner)
            # This command is confined to the disposable TMUX_TMPDIR namespace.
            child = await asyncio.create_subprocess_exec("tmux", "-L", "default", "kill-server", env=env,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await asyncio.wait_for(child.wait(), 5)

    # Pure installed owner-state cases have a separate evidence class, no actual collection.
    from tmux_observer._owner_state import OwnerState
    fixture = Publisher("tmux", "beta", profile=profile).frame
    state = OwnerState(fixture["source"], fixture["clock"])
    for label, value in [("warming", state.frame(boottime_ms()))]:
        report["pureOwnerCases"].append({"case": label, "nativeHealth": [r["health"] for r in codec.inspect_native(value).receipts]})
    # Rebase initialization into the past; frame() alone performs actual installed expiry logic.
    snapshot = fixture["snapshot"]
    shift = 20000
    snapshot["sample"]["startedAt"] -= shift
    snapshot["sample"]["finishedAt"] -= shift
    token = state.begin(snapshot["sample"]["startedAt"])
    assert state.finish(token, snapshot, snapshot["sample"]["finishedAt"] + 1)
    expired = state.frame(boottime_ms())
    report["pureOwnerCases"].append({"case": "expired", "nativeHealth": [r["health"] for r in codec.inspect_native(expired).receipts]})
    for label, result in (("failed", "failed"), ("unsupported", "unsupported")):
        state.failure("collection_failed", "owned fixture failure", result)
        value = state.frame(boottime_ms())
        report["pureOwnerCases"].append({"case": label, "nativeHealth": [r["health"] for r in codec.inspect_native(value).receipts]})
    report["rawMatches"] = sum(pair["rawDigestMatch"] for pair in report["pairs"])
    report["partialNativeState"] = "not a declared Tmux service receipt state; no invented partial native fixture"
    report["declaredPublisherCapabilities"] = list(source.capabilities)
    report["compactFacade"] = "no reviewed stable-state/overlay interface in pinned SDK/profile; no generic exclusions applied"
    report["cleanup"] = True
    report["scriptSha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "pairs": len(report["pairs"]), "rawMatches": report["rawMatches"], "cleanup": True}))


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.is_absolute() or args.output.exists():
        parser.error("new_absolute_output")
    asyncio.run(run(args))
