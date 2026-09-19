"""
Module: scripts/level9_plan.py

Prices the Level 9 grid, including the convergence threshold sweep.

Two things are decided here rather than discovered mid run. The first is the
threshold sweep. No analysis has reached the 0.8 convergence threshold across
26496 mock iterations, 128 real ones and now 43335 model calls in the clock
study, so convergence fraction is 0.0000 everywhere and two of the eight
outcome metrics cannot move while the threshold is a constant. Sweeping it
over values that bracket the observed ceiling is what makes them measurable.

The second is the shape of the grid. The full factorial at every threshold is
priced first; if it does not fit, the fallback is stated explicitly rather
than chosen after seeing which cells are interesting.

Cache behaviour is predicted structurally rather than assumed. L6.8 reasoned,
and L7.8.7 measured, that the U and P switches change no prompt: persistence
affects only convergence gating and the existing hypothesis context already
filters UNKNOWN out. S and A both alter the confidences printed into the next
iteration's prompt and are the only switches that cost calls. The threshold
behaves like U and P for the first iteration and can only shorten an
analysis, never lengthen it, so it adds no new prompts of its own.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from itertools import product
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "level9_prep"

SWITCHES = ("U", "S", "A", "P")
PROMPT_CHANGING = ("S", "A")
THRESHOLDS = (0.30, 0.50, 0.80)

MEASURED_LATENCY = 8.927
MEASURED_RPM_CEILING = 728.7
LEVEL8_UNITS = 600
LEVEL8_PREDICTED_CRITICAL_PATH = 2009.0
LEVEL8_ACTUAL = 1980.0


def expected_hit_rate(configurations: int, seeds: int, thresholds: int) -> dict[str, Any]:
    """Predict the share of calls the cache serves, from switch structure.

    A prompt is identified by the situation, the iteration and the confidences
    printed into it. Only S and A change those, so the sixteen configurations
    collapse into four distinct prompt families, one per S and A combination.
    Everything else in the grid, the U and P switches, the seeds within a
    prompt family and the thresholds, reuses a family that has already been
    paid for, except that seeds are deliberately given their own caches so
    that the five replicates stay independent.
    """
    families = 2 ** len(PROMPT_CHANGING)
    paid_fraction = families / configurations
    return {
        "distinct_prompt_families": families,
        "configurations": configurations,
        "prompt_changing_switches": list(PROMPT_CHANGING),
        "free_switches": [s for s in SWITCHES if s not in PROMPT_CHANGING],
        "share_of_configurations_that_must_be_paid": round(paid_fraction, 4),
        "predicted_hit_rate_within_a_seed": round(1.0 - paid_fraction, 4),
        "measured_comparison": {
            "l7_8_7_per_switch_real": 0.9092,
            "l8_clock_study_real": 0.8908,
            "l6_8_mock_upper_bound": 0.936,
        },
        "caveat": (
            "Caches are scoped per seed so the five replicates remain "
            "independent draws, which means the paid fraction is paid once "
            "per seed rather than once for the grid."
        ),
    }


def main() -> int:
    """Price the grid and write the plan."""
    parser = argparse.ArgumentParser(description="Level 9 grid plan.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=40)
    parser.add_argument("--budget-hours", type=float, default=24.0)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)

    calls_per_scenario = {s.scenario_id: 3 * len(s.signals) for s in scenarios}
    calls_per_pass = sum(calls_per_scenario.values())
    longest_unit = max(calls_per_scenario.values())
    configurations = 2 ** len(SWITCHES)

    hit = expected_hit_rate(configurations, args.seeds, len(THRESHOLDS))
    paid_share = hit["share_of_configurations_that_must_be_paid"]

    options: list[dict[str, Any]] = []
    for label, thresholds, seeds in (
        ("full factorial at every threshold", len(THRESHOLDS), args.seeds),
        ("full factorial, threshold sweep at one seed", len(THRESHOLDS), 1),
        ("threshold sweep on the all on configuration only", len(THRESHOLDS), args.seeds),
    ):
        if label.startswith("threshold sweep on"):
            grid_configurations = 1
        else:
            grid_configurations = configurations
        units = grid_configurations * seeds * thresholds * len(scenarios)
        total_calls = grid_configurations * seeds * thresholds * calls_per_pass
        if label == "full factorial, threshold sweep at one seed":
            units = configurations * (
                args.seeds + (thresholds - 1) * seeds
            ) * len(scenarios)
            total_calls = configurations * (
                args.seeds + (thresholds - 1) * seeds
            ) * calls_per_pass
        paid_calls = total_calls * paid_share
        wall = max(
            paid_calls * MEASURED_LATENCY / args.concurrency,
            paid_calls / MEASURED_RPM_CEILING * 60.0,
            longest_unit * MEASURED_LATENCY,
        )
        options.append(
            {
                "seed": args.seed,
                "option": label,
                "configurations": grid_configurations,
                "thresholds": thresholds,
                "seeds_on_sweep": seeds,
                "units": units,
                "calls_if_all_missed": round(total_calls),
                "calls_actually_paid": round(paid_calls),
                "predicted_wall_clock_hours": round(wall / 3600, 3),
                "fits_budget": bool(wall / 3600 <= args.budget_hours),
            }
        )

    recommended = next((o for o in options if o["fits_budget"]), None)

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "scenarios": len(scenarios),
        "calls_per_pass": calls_per_pass,
        "longest_unit_calls": longest_unit,
        "switches": list(SWITCHES),
        "configurations": configurations,
        "thresholds_swept": list(THRESHOLDS),
        "threshold_rationale": (
            "The real model ceiling was 0.385 in L7.8 and 0.4620 in the clock "
            "study, and the convergence fraction is 0.0000 at 0.80. These "
            "three values bracket the observed range: 0.30 sits below every "
            "ceiling measured, 0.50 sits just above them, and 0.80 is the "
            "current constant and the control."
        ),
        "seeds": args.seeds,
        "concurrency": args.concurrency,
        "measured_inputs": {
            "seconds_per_model_call": MEASURED_LATENCY,
            "requests_per_minute_ceiling": MEASURED_RPM_CEILING,
            "level8_units": LEVEL8_UNITS,
            "level8_predicted_critical_path_seconds": LEVEL8_PREDICTED_CRITICAL_PATH,
            "level8_actual_wall_clock_seconds": LEVEL8_ACTUAL,
            "level8_ratio": round(LEVEL8_ACTUAL / LEVEL8_PREDICTED_CRITICAL_PATH, 3),
        },
        "predicted_critical_path_seconds": round(longest_unit * MEASURED_LATENCY, 1),
        "cache": hit,
        "options": options,
        "recommended": recommended,
    }
    (RESULTS_DIR / f"level9_plan_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    csv_path = RESULTS_DIR / f"level9_plan_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(options[0].keys()))
        writer.writeheader()
        writer.writerows(options)

    print(f"seed {args.seed}   suite {suite_path.name}   scenarios {len(scenarios)}")
    print(f"calls per pass {calls_per_pass}   longest unit {longest_unit} calls")
    print(f"switches {list(SWITCHES)}   configurations {configurations}")
    print(f"thresholds swept {list(THRESHOLDS)}")
    print()
    print("cache prediction from switch structure")
    print(f"  prompt changing switches   {hit['prompt_changing_switches']}")
    print(f"  free switches              {hit['free_switches']}")
    print(f"  distinct prompt families   {hit['distinct_prompt_families']} of {configurations}")
    print(f"  predicted hit rate         {hit['predicted_hit_rate_within_a_seed']}")
    print(f"  measured for comparison    L7.8.7 {hit['measured_comparison']['l7_8_7_per_switch_real']}"
          f"  L8 {hit['measured_comparison']['l8_clock_study_real']}")
    print()
    header = f"{'option':<46}{'units':>8}{'paid calls':>12}{'hours':>9}{'fits':>7}"
    print(header)
    print("-" * len(header))
    for option in options:
        print(
            f"{option['option']:<46}{option['units']:>8}"
            f"{option['calls_actually_paid']:>12}"
            f"{option['predicted_wall_clock_hours']:>9.2f}"
            f"{str(option['fits_budget']):>7}"
        )
    print()
    print(f"predicted critical path {report['predicted_critical_path_seconds']:.0f} s")
    print(
        f"Level 8 validation: predicted {LEVEL8_PREDICTED_CRITICAL_PATH:.0f} s, "
        f"actual {LEVEL8_ACTUAL:.0f} s, ratio {report['measured_inputs']['level8_ratio']}"
    )
    print()
    if recommended:
        print(f"RECOMMENDED {recommended['option']}")
        print(
            f"  {recommended['units']} units, {recommended['calls_actually_paid']} paid "
            f"calls, {recommended['predicted_wall_clock_hours']:.2f} h"
        )
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
