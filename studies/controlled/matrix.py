"""Balanced fresh-resource carrier blocks with fail-closed exact trace qualification."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace import canonical  # noqa: E402

from run import case, inputs  # noqa: E402


def workload(value):
    return {"rows": value["rows"], "steps": value["steps"], "mode": value["mode"], "fanout": value["fanout"],
            "trace": value["trace"], "proofs": value["traffic"]["proofRequests"],
            "pushes": value["traffic"].get("received:data", 0),
            "nativeSnapshots": value["sourceCountsAfter"]["snapshot"] - value["sourceCountsBefore"]["snapshot"],
            "consumerAdmissions": value["consumerAdmissions"]}


def qualify(values):
    if len(values) != 4 or [v["position"] for v in values] != [0, 1, 2, 3]:
        raise ValueError("matrix_block_positions")
    if [v["carrier"] for v in values] != [values[0]["carrier"], values[1]["carrier"], values[1]["carrier"], values[0]["carrier"]]:
        raise ValueError("matrix_block_order")
    if values[0]["carrier"] == values[1]["carrier"]:
        raise ValueError("matrix_block_carriers")
    if any(v["status"] != "passed" or not v["cleanup"] for v in values):
        raise ValueError("matrix_case_not_accepted")
    if any(workload(v) != workload(values[0]) for v in values[1:]):
        raise ValueError("matrix_workload_mismatch")


async def run(args):
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise ValueError("output_not_empty")
    (args.output / "inputs.json").write_text(json.dumps(inputs(), indent=2) + "\n")
    completed = []
    for pair in args.pairs:
        a, b = pair.split("-")
        for mode in args.modes:
            for fanout in args.fanout:
                for block in range(args.blocks):
                    values = []
                    for position, carrier in enumerate((a, b, b, a)):
                        label = f"{pair}-{mode}-{fanout}-{block}-{position}"
                        try:
                            value = await case(args, carrier, fanout, mode)
                            value.update(pair=pair, block=block, position=position)
                        except Exception as error:
                            (args.output / (label + ".json")).write_text(json.dumps({"status": "failed", "error": str(error)}, indent=2) + "\n")
                            raise
                        (args.output / (label + ".json")).write_text(json.dumps(value, indent=2) + "\n")
                        values.append(value)
                    qualify(values)
                    completed.append({"pair": pair, "mode": mode, "fanout": fanout, "block": block, "status": "matched"})
                    (args.output / "index.json").write_text(json.dumps(completed, indent=2) + "\n")
                    print(canonical(completed[-1]), flush=True)


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs", nargs="+", choices=("ipc-ssh", "ssh-wss"), default=["ipc-ssh", "ssh-wss"])
    parser.add_argument("--modes", nargs="+", choices=("poll", "push"), default=["poll", "push"])
    parser.add_argument("--fanout", nargs="+", type=int, choices=(1, 2, 4), default=[1, 2, 4])
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--interval", type=float, default=.05)
    args = parser.parse_args()
    if not args.output.is_absolute() or not 1 <= args.blocks <= 4 or not 1 <= args.steps <= 100 or not .01 <= args.interval <= .1:
        parser.error("bounded_matrix_inputs")
    asyncio.run(run(args))
