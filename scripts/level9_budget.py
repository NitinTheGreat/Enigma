"""
Module: scripts/level9_budget.py

Sizes Level 8 and Level 9 against measured throughput rather than a guess.

The constraint chain. A pass over a suite costs three model calls per signal,
because every arriving signal triggers an analysis and every analysis runs to
its three iteration budget. The cache removes the calls whose prompt has been
seen before. What remains is divided by the achievable concurrency, and the
result is floored by the tier's requests per minute, because no amount of
concurrency buys throughput the tier will not serve.

    calls        = 3 * signals * passes
    uncached     = calls * (1 - hit_rate)
    wall_seconds = max(uncached * latency / concurrency, uncached / rpm * 60)

Every input is measured, not assumed. Latency and hit rate come from the real
path recorded in results/scenarios, the requests per minute ceiling from
results/budget/rate_limit_seed42.json, and the calls per scenario from a
fallback pass over the sub-suite, which costs nothing and counts exactly.

Passes. Level 8 varies three clock modes. Level 9 varies sixteen epistemic
configurations, and the convergence threshold now varies with them: no
analysis has ever reached the 0.8 threshold across 26496 mock and 128 real
iterations, so holding it constant pins single_iteration_conclusion_rate at
0.0 and mean_iterations_to_termination at 3.0 and two of the eight outcome
metrics cannot move. The sweep is what makes them measurable.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "budget"
SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"

ITERATIONS_PER_ANALYSIS = 3
SIGNALS_PER_SCENARIO = 1460 / 60
REGIMES = 4
LEVEL8_MODES = 3
LEVEL9_CONFIGURATIONS = 16


def measured_rpm(path: Path, fallback: float) -> tuple[float, str]:
    """Read the achieved requests per minute from the rate limit probe."""
    if not path.is_file():
        return fallback, "not measured, default assumed"
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("refused", 0) == 0:
        note = (
            f"no refusal at {report['achieved_requests_per_minute']} rpm, "
            f"concurrency {report['concurrency']}, so this is a floor"
        )
    else:
        note = f"refused {report['refused']} of {report['requests']}"
    return float(report["achieved_requests_per_minute"]), note


def measured_real_run(path: Path) -> dict[str, Any]:
    """Read latency and cache behaviour from the scored real run."""
    if not path.is_file():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    cache = report.get("cache") or {}
    return {
        "seconds_per_model_call": report.get("seconds_per_model_call"),
        "model_calls": report.get("model_calls"),
        "cache_hit_rate": cache.get("hit_rate"),
        "elapsed_seconds": report.get("elapsed_seconds"),
    }


def wall_seconds(
    calls: float, hit_rate: float, latency: float, concurrency: int, rpm: float
) -> float:
    """Return the wall clock a pass count costs under these constraints."""
    uncached = calls * (1.0 - hit_rate)
    by_latency = uncached * latency / max(concurrency, 1)
    by_rate = uncached / rpm * 60.0 if rpm > 0 else float("inf")
    return max(by_latency, by_rate)


def main() -> int:
    """Enumerate the budget grid and recommend a configuration."""
    parser = argparse.ArgumentParser(description="Level 8 and Level 9 budget.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--latency", type=float, default=0.0)
    parser.add_argument("--rpm", type=float, default=0.0)
    parser.add_argument("--hit-rate", type=float, default=-1.0)
    parser.add_argument("--level9-hours", type=float, default=24.0)
    parser.add_argument("--level8-hours", type=float, default=6.0)
    parser.add_argument("--threshold-values", type=int, default=3)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    rpm, rpm_note = measured_rpm(
        RESULTS_DIR / f"rate_limit_seed{args.seed}.json", args.rpm or 450.0
    )
    if args.rpm:
        rpm, rpm_note = args.rpm, "supplied on the command line"

    real = measured_real_run(SCENARIOS_DIR / "validation_run_real.json")
    latency = args.latency or real.get("seconds_per_model_call") or 8.49
    if args.hit_rate >= 0:
        hit_measured = args.hit_rate
        hit_note = "supplied on the command line"
    elif real.get("cache_hit_rate") is not None:
        hit_measured = float(real["cache_hit_rate"])
        hit_note = "measured on the real path, cold cache"
    else:
        hit_measured = 0.0
        hit_note = "not measured, cold cache assumed"

    per_regime_grid = (5, 10, 15, 25, 50, 100)
    seed_grid = (3, 5)
    concurrency_grid = (1, 10, 25, 50)
    hit_grid = (
        (round(hit_measured, 4), hit_note),
        (0.936, "L6.8 upper bound, mock inflated"),
    )

    rows: list[dict[str, Any]] = []
    for per_regime in per_regime_grid:
        scenarios = per_regime * REGIMES
        signals = scenarios * SIGNALS_PER_SCENARIO
        calls_per_pass = ITERATIONS_PER_ANALYSIS * signals
        for seeds in seed_grid:
            l8_passes = LEVEL8_MODES * seeds
            l9_passes = LEVEL9_CONFIGURATIONS * seeds * args.threshold_values
            for concurrency in concurrency_grid:
                for hit, label in hit_grid:
                    l8 = wall_seconds(
                        calls_per_pass * l8_passes, hit, latency, concurrency, rpm
                    )
                    l9 = wall_seconds(
                        calls_per_pass * l9_passes, hit, latency, concurrency, rpm
                    )
                    rows.append(
                        {
                            "seed": args.seed,
                            "situations_per_regime": per_regime,
                            "scenarios": scenarios,
                            "signals": round(signals),
                            "calls_per_pass": round(calls_per_pass),
                            "seeds": seeds,
                            "concurrency": concurrency,
                            "cache_hit_rate": hit,
                            "cache_hit_source": label,
                            "level8_passes": l8_passes,
                            "level8_calls": round(calls_per_pass * l8_passes),
                            "level8_hours": round(l8 / 3600, 2),
                            "level9_passes": l9_passes,
                            "level9_calls": round(calls_per_pass * l9_passes),
                            "level9_hours": round(l9 / 3600, 2),
                            "within_budget": bool(
                                l9 / 3600 <= args.level9_hours
                                and l8 / 3600 <= args.level8_hours
                            ),
                        }
                    )

    feasible = [
        r
        for r in rows
        if r["within_budget"] and r["cache_hit_rate"] == hit_grid[0][0]
    ]
    recommended = None
    if feasible:
        recommended = max(
            feasible,
            key=lambda r: (
                r["situations_per_regime"],
                r["seeds"],
                -r["concurrency"],
            ),
        )

    csv_path = RESULTS_DIR / f"level9_budget_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "seed": args.seed,
        "generated_at_utc": started.isoformat(),
        "measured_inputs": {
            "seconds_per_model_call": latency,
            "requests_per_minute": rpm,
            "requests_per_minute_note": rpm_note,
            "cache_hit_rate": hit_measured,
            "cache_hit_rate_note": hit_note,
            "signals_per_scenario": round(SIGNALS_PER_SCENARIO, 4),
            "iterations_per_analysis": ITERATIONS_PER_ANALYSIS,
        },
        "targets": {
            "level8_hours": args.level8_hours,
            "level9_hours": args.level9_hours,
        },
        "level9_threshold_values_swept": args.threshold_values,
        "rows": rows,
        "recommended": recommended,
        "recommendation_basis": (
            "measured cache hit rate only. The 0.936 rows are carried in the "
            "grid for comparison and are never recommended from, because L6.8 "
            "records that figure as a mock inflated upper bound."
        ),
    }
    json_path = RESULTS_DIR / f"level9_budget_seed{args.seed}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"seed {args.seed}")
    print(f"latency {latency} s per call   rpm ceiling {rpm} ({rpm_note})")
    print(f"cache hit rate {hit_measured} ({hit_note})")
    print(f"level 9 sweeps {args.threshold_values} convergence thresholds")
    print()
    header = (
        f"{'per regime':>10}{'scen':>6}{'calls/pass':>11}{'seeds':>6}"
        f"{'conc':>6}{'hit':>7}{'L8 h':>8}{'L9 h':>9}{'fits':>6}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        if row["cache_hit_rate"] != hit_grid[0][0]:
            continue
        print(
            f"{row['situations_per_regime']:>10}{row['scenarios']:>6}"
            f"{row['calls_per_pass']:>11}{row['seeds']:>6}{row['concurrency']:>6}"
            f"{row['cache_hit_rate']:>7}{row['level8_hours']:>8}"
            f"{row['level9_hours']:>9}{'yes' if row['within_budget'] else 'no':>6}"
        )
    print()
    if recommended:
        print("recommended")
        print(json.dumps(recommended, indent=2))
    else:
        print("no combination in the grid meets both targets")
    print()
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"written {json_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
