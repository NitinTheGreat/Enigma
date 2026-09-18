"""
Module: scripts/level6_latency_report.py

Renders the six stage latency table from the runs that produced it.

No single run covers all six boundaries. The offline replay has no dashboard,
so it cannot time a broadcast, and the load harness substitutes a fixed service
time for the model, so its reasoning stage measures the substitute rather than
the model. Both are reported, each labelled with what it actually measured,
rather than merged into one table that would imply a run which never happened.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "level6"

STAGE_ORDER = [
    "signal_ingest",
    "situation_attach",
    "deterministic_reasoning",
    "langgraph_gemini",
    "explanation_build",
    "dashboard_broadcast",
]


def render(title: str, stages: dict) -> None:
    """Print one stage table."""
    print(title)
    header = f"{'stage':<26}{'n':>7}{'p50 ms':>11}{'p95 ms':>11}{'p99 ms':>11}{'max ms':>11}"
    print(header)
    print("-" * len(header))
    for name in STAGE_ORDER:
        row = stages.get(name)
        if row is None:
            print(f"{name:<26}{'not measured':>51}")
            continue
        print(
            f"{name:<26}{row['count']:>7}{row['p50_ms']:>11.3f}"
            f"{row['p95_ms']:>11.3f}{row['p99_ms']:>11.3f}{row['max_ms']:>11.3f}"
        )
    print()


def main() -> int:
    """Load both sources and print the tables."""
    parser = argparse.ArgumentParser(description="Level 6 latency report.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--replay-tag", type=str, default="s100")
    parser.add_argument("--load-rate", type=float, default=4.0)
    args = parser.parse_args()

    replay_path = RESULTS_DIR / f"latency_{args.replay_tag}.json"
    replay_stages = json.loads(replay_path.read_text(encoding="utf-8"))["stages"]

    load_stages = {}
    load_meta = {}
    with (RESULTS_DIR / "queue_depth.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["arrival_rate_per_second"] == args.load_rate:
                load_stages = row["latency_ms"]
                load_meta = row
                break

    print(f"seed {args.seed}")
    print()
    render(
        f"offline replay, tag {args.replay_tag}, "
        f"{replay_stages['langgraph_gemini']['count']} analyses\n"
        "reasoning stage is a real LangGraph pass over a deterministic mock model, "
        "so it excludes network and model time\n"
        "no dashboard exists offline, so no broadcast is timed\n",
        replay_stages,
    )
    render(
        f"load harness at {args.load_rate} records/s, "
        f"{load_meta.get('completed', 0)} analyses\n"
        "reasoning stage is a fixed simulated service time, not a model call\n"
        "every other stage is the real code path\n",
        load_stages,
    )

    combined = {
        "seed": args.seed,
        "offline_replay": {
            "tag": args.replay_tag,
            "reasoning_stage_measures": "langgraph over deterministic mock model",
            "broadcast_measured": False,
            "stages": replay_stages,
        },
        "load_harness": {
            "arrival_rate_per_second": args.load_rate,
            "reasoning_stage_measures": "fixed simulated service time",
            "broadcast_measured": True,
            "stages": load_stages,
        },
        "real_model_latency": "UNVERIFIED, no Gemini API key in this environment",
    }
    (RESULTS_DIR / "latency_six_stage.json").write_text(
        json.dumps(combined, indent=2), encoding="utf-8"
    )
    print(f"written to {RESULTS_DIR / 'latency_six_stage.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
