"""Repeat an owned Tmux refresh fixture with redacted control-stage diagnostics.

The explicit sibling checkout supplies disposable test sources only. Runtime
imports come from the selected interpreter; no ordinary services are refreshed.
"""

import argparse
import collections
import hashlib
import json
import sys
import time
import traceback
import unittest
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmux-checkout", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--transport", choices=("mesh", "legacy"), default="mesh")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 1000:
        parser.error("repetitions must be 1..1000")
    sys.path.insert(0, str(args.tmux_checkout / "tests"))
    from test_fleet import FleetTests

    sys.path.insert(0, str(args.tmux_checkout / "tests_mesh"))
    from test_fleet_mesh import MeshFleetTests
    from tmux_observer_client import _mesh_control
    from tmux_observer_client._fleet_tickets import FleetTickets
    from tmux_observer_client._mesh_projection import MeshOwnerState
    from tmux_observer_client._mesh_worker import MeshWorker
    from tmux_observer_client.mesh_fleet import MeshFleetPublisher

    counts = collections.Counter()
    recent = collections.deque(maxlen=128)
    failures = []
    receive, fail = FleetTickets.receive, FleetTickets.fail_host
    validate = _mesh_control.validate_service_frame
    poll = _mesh_control.OwnerControl.poll
    put = MeshWorker.put
    project = MeshOwnerState.accept_mesh
    catalog_failure = MeshFleetPublisher.catalog_failure

    def inspect_catalog_failure(self, now, code, message):
        counts["catalog_failure:" + code] += 1
        recent.append({"stage": "catalog_failure", "code": code})
        return catalog_failure(self, now, code, message)

    def inspect_project(self, host, rows, **kwargs):
        before = self.epoch, self.scope, self.selected_route
        try:
            result = project(self, host, rows, **kwargs)
        except (ValueError, TypeError, KeyError) as error:
            counts["projection_failure:" + type(error).__name__] += 1
            recent.append(
                {
                    "stage": "projection",
                    "failureType": type(error).__name__,
                    "trace": [
                        {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                        for frame in traceback.extract_tb(error.__traceback__)[-6:]
                    ],
                }
            )
            raise
        after = self.epoch, self.scope, self.selected_route
        if before != after:
            recent.append(
                {
                    "stage": "projection_binding",
                    "oldEpoch": before[0],
                    "newEpoch": after[0],
                    "scopeChanged": before[1] != after[1],
                    "scopePresent": after[1] is not None,
                    "delivery": host["delivery"]["status"],
                }
            )
        return result

    class DiagnosticResult(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.exception_stages = []

        def record_exception(self, err):
            self.exception_stages.append(
                {
                    "failureType": err[0].__name__,
                    "trace": [
                        {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                        for frame in traceback.extract_tb(err[2])[-8:]
                    ],
                }
            )

        def addFailure(self, test, err):
            self.record_exception(err)
            super().addFailure(test, err)

        def addError(self, test, err):
            self.record_exception(err)
            super().addError(test, err)

    def inspect_put(self, event):
        if event[0] == "view":
            for host in event[1]["mesh"]["hosts"]:
                delivery = host["delivery"]
                if delivery["status"] != "ready":
                    recent.append(
                        {
                            "stage": "mesh_delivery",
                            "status": delivery["status"],
                            "code": (delivery.get("error") or {}).get("code"),
                            "epoch": delivery["epoch"],
                        }
                    )
        elif event[0] == "error":
            recent.append({"stage": "mesh_worker_error", "code": event[1]})
        return put(self, event)

    def inspect_poll(self, now):
        if self.future is not None and self.future.done() and not self.closed:
            try:
                value = self.future.result()
                scope = self.state.scope
                recent.append(
                    {
                        "stage": "control_reply",
                        "kind": value.get("kind"),
                        "sequence": value.get("sequence"),
                        "requestMatches": value.get("requestId") == self.request["requestId"],
                        "publisherMatches": value.get("publisherId") == self.request["publisherId"],
                        "scopePresent": scope is not None,
                        "bindingMatches": self.binding
                        == (self.state.epoch, scope, self.state.selected_route),
                        "scopeMatches": scope is not None
                        and (
                            value["source"]["uid"],
                            value["source"]["server"],
                            value["clock"]["bootId"],
                            value["clock"]["timeNamespace"],
                        )
                        == scope[1:],
                    }
                )
            except Exception as error:
                counts["control_exchange_failure:" + type(error).__name__] += 1
                recent.append(
                    {
                        "stage": "control_exchange",
                        "failureType": type(error).__name__,
                        "trace": [
                            {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                            for frame in traceback.extract_tb(error.__traceback__)[-8:]
                        ],
                    }
                )
        return poll(self, now)

    def inspect_receive(self, connection, value, matched, now):
        child = self.children.get(connection.state.host_id)
        ticket = value.get("ticket")
        if child is not None and ticket is not None:
            old = child.ticket
            event = {
                "stage": "ticket_receive",
                "kind": value["kind"],
                "ack": value["requestId"] == child.request_id,
                "lookup": child.lookup_id is not None and value["requestId"] == child.lookup_id,
                "old": None if old is None else [(r["state"], r["attempt"]) for r in old["sources"]],
                "new": [(r["state"], r["attempt"]) for r in ticket["sources"]],
            }
            recent.append(event)
            counts["ticket_receive"] += 1
        return receive(self, connection, value, matched, now)

    def inspect_fail(self, host, now, **kwargs):
        code = kwargs.get("code", "owner_unavailable")
        counts["ticket_failure:" + code] += 1
        # Only fixed implementation messages; no native payload or exception text.
        recent.append(
            {
                "stage": "ticket_failure",
                "code": code,
                "reason": kwargs.get("message", "owner source unavailable"),
            }
        )
        return fail(self, host, now, **kwargs)

    def inspect_validation(value):
        try:
            result = validate(value)
        except (ValueError, TypeError, KeyError) as error:
            counts["control_validation_failure:" + type(error).__name__] += 1
            recent.append({"stage": "control_validation", "failureType": type(error).__name__})
            raise
        counts["control_validation_passed"] += 1
        return result

    paths = [args.tmux_checkout / "tests" / name for name in ("test_fleet.py", "test_owner.py")]
    paths += [
        args.tmux_checkout / "tests_mesh/test_fleet_mesh.py",
        Path(_mesh_control.__file__),
        Path(sys.modules[FleetTickets.__module__].__file__),
    ]
    input_digests = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    harness_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    started = time.monotonic()
    with (
        patch.object(FleetTickets, "receive", inspect_receive),
        patch.object(FleetTickets, "fail_host", inspect_fail),
        patch.object(_mesh_control.OwnerControl, "poll", inspect_poll),
        patch.object(MeshWorker, "put", inspect_put),
        patch.object(_mesh_control, "validate_service_frame", inspect_validation),
        patch.object(MeshOwnerState, "accept_mesh", inspect_project),
        patch.object(MeshFleetPublisher, "catalog_failure", inspect_catalog_failure),
    ):
        for index in range(args.repetitions):
            recent.clear()
            test = (
                MeshFleetTests("test_grouped_refresh_requires_mesh_confirmed_native_attempt")
                if args.transport == "mesh"
                else FleetTests("test_grouped_refresh_reconciles_desktop_after_actual_owner_sample")
            )
            result = DiagnosticResult()
            test.run(result)
            if not result.wasSuccessful():
                failures.append(
                    {
                        "iteration": index + 1,
                        "failures": len(result.failures),
                        "errors": len(result.errors),
                        "exceptionStages": result.exception_stages,
                        "events": list(recent),
                    }
                )
            if (index + 1) % 10 == 0:
                print(json.dumps({"completed": index + 1, "failed": len(failures)}), flush=True)
    report = {
        "format": "mesh-plus.refresh-investigation.v1",
        "repetitions": args.repetitions,
        "transport": args.transport,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "failed": len(failures),
        "counts": dict(counts),
        "failures": failures,
        "python": sys.version.split()[0],
        "inputDigests": input_digests,
        "inputPathsUnchangedAtCompletion": input_digests
        == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "harnessSha256": harness_digest,
        "limits": [
            "Owned synthetic owner/fleet Unix services; no ordinary refresh or native collection",
            "Bounded ticket state/attempt trace; no session records or arbitrary exception text",
            "Passing exposure does not explain an unreproduced operational failure",
        ],
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
