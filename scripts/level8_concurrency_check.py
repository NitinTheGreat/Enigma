"""
Module: scripts/level8_concurrency_check.py

Proves the concurrent driver does the same work as the serial one.

The claim under test is not that two runs produce identical files. They do
not, and must not be expected to: workers interleave, so the run log's line
order differs and so does the wall clock. The claim is that the same seed
produces the same set of analyses, each identified by its situation, the
evidence it terminated on, the iteration it reached and why it stopped.

Both runs are driven through the deterministic mock rather than Gemini. A
real model is sampled and would differ between runs for reasons that have
nothing to do with concurrency, which would make the comparison prove
nothing. Throughput against the real model is measured separately by
level8_throughput.py, where variation is expected and only the rate matters.

Everything is written to results/budget as JSON and CSV, with the seed in
both the filename and the payload.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter  # noqa: E402
from enigma_reason.replay.concurrent import ConcurrentReplay, analysis_keys  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay, mock_llm_factory  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "budget"


def run_at(concurrency: int, scenarios: list[Any], seed: int, log_path: Path) -> dict[str, Any]:
    """Run the suite at one concurrency and return what it did."""
    if log_path.exists():
        log_path.unlink()

    controls = EpistemicControls()
    started = time.monotonic()
    with RunLogWriter(log_path) as writer:

        def build_replay(unit: str, unit_factory):
            """Create one scenario's replay with its own store and engine."""
            return OfflineReplay(
                unit_factory,
                run_log=writer,
                seed=seed,
                correlation=EntityCorrelation(),
                controls=controls,
            )

        analyses = 0
        retries = 0
        if concurrency > 1:
            driver = ConcurrentReplay(
                build_replay,
                mock_llm_factory(seed=seed),
                concurrency=concurrency,
                run_log=writer,
            )
            outcome = driver.run(
                [(s.scenario_id, s.signals) for s in scenarios]
            )
            analyses = outcome.analyses_run
            retries = len(outcome.retries)
        else:
            for scenario in scenarios:
                replay = build_replay(scenario.scenario_id, mock_llm_factory(seed=seed))
                analyses += replay.run(scenario.signals).analyses_run
        writer.flush()
        iterations = writer.written
    elapsed = time.monotonic() - started

    keys = analysis_keys(log_path)
    return {
        "concurrency": concurrency,
        "analyses_run": analyses,
        "iterations_logged": iterations,
        "retries": retries,
        "wall_clock_seconds": round(elapsed, 3),
        "analysis_keys": keys,
        "distinct_analyses": len(keys),
    }


def main() -> int:
    """Compare the serial and concurrent drivers on the same seed."""
    parser = argparse.ArgumentParser(description="Concurrency determinism check.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)

    serial = run_at(1, scenarios, args.seed, RESULTS_DIR / f"conc1_seed{args.seed}.jsonl")
    parallel = run_at(
        args.concurrency,
        scenarios,
        args.seed,
        RESULTS_DIR / f"conc{args.concurrency}_seed{args.seed}.jsonl",
    )

    identical = serial["analysis_keys"] == parallel["analysis_keys"]
    only_serial = sorted(set(serial["analysis_keys"]) - set(parallel["analysis_keys"]))
    only_parallel = sorted(set(parallel["analysis_keys"]) - set(serial["analysis_keys"]))
    speedup = (
        serial["wall_clock_seconds"] / parallel["wall_clock_seconds"]
        if parallel["wall_clock_seconds"]
        else 0.0
    )

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "scenarios": len(scenarios),
        "model": "Level 6 deterministic mock",
        "serial": {k: v for k, v in serial.items() if k != "analysis_keys"},
        "parallel": {k: v for k, v in parallel.items() if k != "analysis_keys"},
        "sorted_analysis_sets_identical": identical,
        "only_in_serial": only_serial[:20],
        "only_in_parallel": only_parallel[:20],
        "speedup": round(speedup, 2),
    }
    (RESULTS_DIR / f"concurrency_check_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    with (RESULTS_DIR / f"concurrency_check_seed{args.seed}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["seed", "concurrency", "analyses_run", "iterations_logged",
             "distinct_analyses", "retries", "wall_clock_seconds"]
        )
        for row in (serial, parallel):
            writer.writerow(
                [args.seed, row["concurrency"], row["analyses_run"],
                 row["iterations_logged"], row["distinct_analyses"],
                 row["retries"], row["wall_clock_seconds"]]
            )

    print(f"seed {args.seed}   suite {suite_path.name}   scenarios {len(scenarios)}")
    print(f"model {report['model']}")
    print()
    header = f"{'concurrency':>12}{'analyses':>10}{'iterations':>12}{'distinct':>10}{'retries':>9}{'wall s':>10}"
    print(header)
    print("-" * len(header))
    for row in (serial, parallel):
        print(
            f"{row['concurrency']:>12}{row['analyses_run']:>10}"
            f"{row['iterations_logged']:>12}{row['distinct_analyses']:>10}"
            f"{row['retries']:>9}{row['wall_clock_seconds']:>10}"
        )
    print()
    print(f"sorted analysis sets identical: {identical}")
    if not identical:
        print(f"  only in serial   {len(only_serial)}: {only_serial[:5]}")
        print(f"  only in parallel {len(only_parallel)}: {only_parallel[:5]}")
    print(f"speedup {report['speedup']}x")
    return 0 if identical else 2


if __name__ == "__main__":
    raise SystemExit(main())
