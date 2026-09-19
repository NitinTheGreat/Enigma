"""
Module: scripts/level8_clock_check.py

Establishes whether the clock domain study can run on this suite at all.

The hazard being studied only exists when event time and wall clock disagree.
L2.2 recorded that the official UNSW-NB15 partition carries no Stime or
Ltime, so a replay of it stamps every signal with ingest time and separated
mode degenerates into wall clock mode: there is nothing to separate. A study
run on such a suite would report three identical configurations and the null
would look like a finding.

Level 7 states its generator emits genuine event timestamps. This checks that
directly rather than trusting it, by reading the frozen sub-suite and
reporting the range of event timestamps it carries and the gap between that
range and the wall clock the study would run at.

The gate. A gap of hours or more means the conflation is demonstrable and the
study is worth running. A gap of seconds means every situation is recent in
both domains, quiet detection cannot diverge between modes, and the level
must not run on this suite.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "clock_study"

MINIMUM_GAP_HOURS = 1.0


def main() -> int:
    """Report the event time range and the gap to wall clock."""
    parser = argparse.ArgumentParser(description="Level 8 clock domain gate.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    parser.add_argument("--minimum-gap-hours", type=float, default=MINIMUM_GAP_HOURS)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()

    scenarios = load_suite(suite_path)
    now = datetime.now(timezone.utc)

    stamps: list[datetime] = []
    per_scenario_span: list[float] = []
    missing = 0
    distinct_by_scenario: Counter[int] = Counter()

    for scenario in scenarios:
        scenario_stamps: list[datetime] = []
        for signal in scenario.signals:
            stamp = getattr(signal, "timestamp", None)
            if stamp is None:
                missing += 1
                continue
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            scenario_stamps.append(stamp)
        if not scenario_stamps:
            continue
        stamps.extend(scenario_stamps)
        distinct_by_scenario[len({s.isoformat() for s in scenario_stamps})] += 1
        per_scenario_span.append(
            (max(scenario_stamps) - min(scenario_stamps)).total_seconds()
        )

    if not stamps:
        print("no event timestamps found in the suite at all")
        return 1

    earliest = min(stamps)
    latest = max(stamps)
    gap_earliest = (now - earliest).total_seconds() / 3600.0
    gap_latest = (now - latest).total_seconds() / 3600.0
    suite_span = (latest - earliest).total_seconds() / 3600.0

    passes = abs(gap_latest) >= args.minimum_gap_hours

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "checked_at_utc": now.isoformat(),
        "scenarios": len(scenarios),
        "signals_with_event_time": len(stamps),
        "signals_missing_event_time": missing,
        "event_time_earliest": earliest.isoformat(),
        "event_time_latest": latest.isoformat(),
        "event_time_span_hours": round(suite_span, 3),
        "gap_to_wall_clock_hours_earliest": round(gap_earliest, 3),
        "gap_to_wall_clock_hours_latest": round(gap_latest, 3),
        "gap_to_wall_clock_days_latest": round(gap_latest / 24.0, 3),
        "per_scenario_span_seconds": {
            "min": round(min(per_scenario_span), 2),
            "median": round(median(per_scenario_span), 2),
            "mean": round(mean(per_scenario_span), 2),
            "max": round(max(per_scenario_span), 2),
        },
        "distinct_timestamps_per_scenario": dict(sorted(distinct_by_scenario.items())),
        "minimum_gap_hours_required": args.minimum_gap_hours,
        "study_can_run": passes,
    }
    json_path = RESULTS_DIR / f"clock_gate_seed{args.seed}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    csv_path = RESULTS_DIR / f"clock_gate_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "quantity", "value"])
        for key in (
            "signals_with_event_time",
            "signals_missing_event_time",
            "event_time_earliest",
            "event_time_latest",
            "event_time_span_hours",
            "gap_to_wall_clock_hours_latest",
            "gap_to_wall_clock_days_latest",
            "study_can_run",
        ):
            writer.writerow([args.seed, key, report[key]])

    print(f"seed {args.seed}   suite {suite_path.name}   scenarios {len(scenarios)}")
    print(f"checked at {now.isoformat()}")
    print()
    print(f"signals with event time     {len(stamps)}")
    print(f"signals missing event time  {missing}")
    print(f"event time earliest         {earliest.isoformat()}")
    print(f"event time latest           {latest.isoformat()}")
    print(f"event time span             {suite_span:.2f} hours")
    print()
    print(f"gap to wall clock, earliest {gap_earliest:.2f} hours")
    print(f"gap to wall clock, latest   {gap_latest:.2f} hours "
          f"({gap_latest / 24.0:.2f} days)")
    print(f"per scenario span seconds   {json.dumps(report['per_scenario_span_seconds'])}")
    print()
    if passes:
        print(
            f"GATE PASS the latest event is {gap_latest:.1f} hours behind wall "
            f"clock, so conflating the two is demonstrable"
        )
    else:
        print(
            f"GATE FAIL the latest event is only {gap_latest:.3f} hours behind "
            f"wall clock, below the {args.minimum_gap_hours} hour minimum. "
            f"Separated and wall mode cannot diverge on this suite."
        )
    print()
    print(f"written {json_path.relative_to(PROJECT_ROOT)}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0 if passes else 2


if __name__ == "__main__":
    raise SystemExit(main())
