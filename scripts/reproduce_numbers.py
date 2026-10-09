"""
Module: scripts/reproduce_numbers.py

Recomputes every number the paper quotes, from committed machine readable
results, and checks each against the value recorded in the evidence file.

This is the reproduction's substance. Regenerating a figure proves the
plotting code runs; recomputing the headline figures and comparing them to
what was written down proves the prose and the data still agree. Each entry
names the appendix it comes from, the file it is read from, and the value
expected, so a mismatch says immediately which claim has drifted.

Nothing here calls a model. Every input is a committed CSV or JSON summary.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"
OUT_DIR = RESULTS / "reproduce"

TOLERANCE = 0.0005


def read_json(path: Path) -> Any:
    """Load a committed JSON summary."""
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    """Load a committed CSV summary."""
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clock_trend_labels(mode: str) -> Callable[[], float]:
    """Return how many distinct trend labels one clock mode emitted."""

    def compute() -> float:
        report = read_json(RESULTS / "clock_study" / "study_seed42.json")
        for summary in report["summaries"]:
            if summary["clock_mode"] == mode:
                return float(len(summary["trend_distribution_pooled"]))
        raise KeyError(mode)

    return compute


def clock_metric(mode: str, field: str) -> Callable[[], float]:
    """Return one pooled clock study quantity."""

    def compute() -> float:
        report = read_json(RESULTS / "clock_study" / "study_seed42.json")
        for summary in report["summaries"]:
            if summary["clock_mode"] == mode:
                return float(summary[field])
        raise KeyError(mode)

    return compute


def ablation_cell(configuration: str, threshold: float, metric: str) -> Callable[[], float]:
    """Return the mean of one ablation cell over its seeds."""

    def compute() -> float:
        rows = read_csv(RESULTS / "ablation" / "cells_seed42.csv")
        values = [
            float(r[metric])
            for r in rows
            if r["configuration"] == configuration
            and abs(float(r["convergence_threshold"]) - threshold) < 1e-9
        ]
        return mean(values)

    return compute


def ablation_effect(switch: str, metric: str, threshold: float) -> Callable[[], float]:
    """Return one main effect from the committed effects table."""

    def compute() -> float:
        rows = read_csv(RESULTS / "ablation" / "main_effects_seed42.csv")
        for r in rows:
            if (
                r["switch"] == switch
                and r["metric"] == metric
                and abs(float(r["convergence_threshold"]) - threshold) < 1e-9
            ):
                return float(r["effect_mean"])
        raise KeyError(switch)

    return compute


def sweep_value(threshold: float, field: str) -> Callable[[], float]:
    """Return one threshold sweep quantity."""

    def compute() -> float:
        rows = read_csv(RESULTS / "ablation" / "threshold_sweep_seed42.csv")
        for r in rows:
            if abs(float(r["convergence_threshold"]) - threshold) < 1e-9:
                return float(r[field])
        raise KeyError(threshold)

    return compute


def context_separation(field: str) -> Callable[[], float]:
    """Return one multivariate separation figure."""

    def compute() -> float:
        report = read_json(RESULTS / "level9_prep" / "context_separation_seed42.json")
        if field.startswith("narrative_"):
            return float(report["narrative_identity"][field[len("narrative_"):]])
        return float(report["multivariate"][field])

    return compute


CLAIMS: list[dict[str, Any]] = [
    {
        "appendix": "L8.4",
        "claim": "conflated emits only two trend labels",
        "source": "results/clock_study/study_seed42.json",
        "expected": 2.0,
        "compute": clock_trend_labels("conflated"),
    },
    {
        "appendix": "L8.4",
        "claim": "separated emits three trend labels",
        "source": "results/clock_study/study_seed42.json",
        "expected": 3.0,
        "compute": clock_trend_labels("separated"),
    },
    {
        "appendix": "L8.4",
        "claim": "conflated marks every situation quiet",
        "source": "results/clock_study/study_seed42.json",
        "expected": 1.0,
        "compute": clock_metric("conflated", "quiet_fraction_mean"),
    },
    {
        "appendix": "L8.5",
        "claim": "conflated abstention rate",
        "source": "results/clock_study/study_seed42.json",
        "expected": 0.5273,
        "compute": clock_metric("conflated", "abstention_rate_mean"),
    },
    {
        "appendix": "L8.5",
        "claim": "separated abstention rate",
        "source": "results/clock_study/study_seed42.json",
        "expected": 0.1818,
        "compute": clock_metric("separated", "abstention_rate_mean"),
    },
    {
        "appendix": "L9.2",
        "claim": "main effect of U on abstention at threshold 0.80",
        "source": "results/ablation/main_effects_seed42.csv",
        "expected": -0.0985,
        "compute": ablation_effect("U", "abstention_rate", 0.80),
    },
    {
        "appendix": "L9.2",
        "claim": "main effect of S on abstention at threshold 0.80",
        "source": "results/ablation/main_effects_seed42.csv",
        "expected": -0.0833,
        "compute": ablation_effect("S", "abstention_rate", 0.80),
    },
    {
        "appendix": "L9.2",
        "claim": "main effect of A on abstention at threshold 0.80",
        "source": "results/ablation/main_effects_seed42.csv",
        "expected": -0.0030,
        "compute": ablation_effect("A", "abstention_rate", 0.80),
    },
    {
        "appendix": "L9.2",
        "claim": "main effect of P on abstention at threshold 0.80 is exactly zero",
        "source": "results/ablation/main_effects_seed42.csv",
        "expected": 0.0,
        "compute": ablation_effect("P", "abstention_rate", 0.80),
    },
    {
        "appendix": "L9.3",
        "claim": "all on abstention rate",
        "source": "results/ablation/cells_seed42.csv",
        "expected": 0.1818,
        "compute": ablation_cell("allon", 0.80, "abstention_rate"),
    },
    {
        "appendix": "L9.3",
        "claim": "minus A is identical to all on",
        "source": "results/ablation/cells_seed42.csv",
        "expected": 0.1818,
        "compute": ablation_cell("A", 0.80, "abstention_rate"),
    },
    {
        "appendix": "L9.3",
        "claim": "minus P is identical to all on",
        "source": "results/ablation/cells_seed42.csv",
        "expected": 0.1818,
        "compute": ablation_cell("P", 0.80, "abstention_rate"),
    },
    {
        "appendix": "L9.3",
        "claim": "minus U takes abstention to zero",
        "source": "results/ablation/cells_seed42.csv",
        "expected": 0.0,
        "compute": ablation_cell("U", 0.80, "abstention_rate"),
    },
    {
        "appendix": "L9.6",
        "claim": "convergence fraction with persistence enabled, threshold 0.30",
        "source": "results/ablation/threshold_sweep_seed42.csv",
        "expected": 0.0,
        "compute": sweep_value(0.30, "convergence_fraction_P_enabled"),
    },
    {
        "appendix": "L9.6",
        "claim": "convergence fraction with persistence ablated, threshold 0.30",
        "source": "results/ablation/threshold_sweep_seed42.csv",
        "expected": 0.5561,
        "compute": sweep_value(0.30, "convergence_fraction_P_ablated"),
    },
    {
        "appendix": "L9.6",
        "claim": "max convergence with persistence enabled is threshold minus 0.01",
        "source": "results/ablation/threshold_sweep_seed42.csv",
        "expected": 0.29,
        "compute": sweep_value(0.30, "max_convergence_P_enabled"),
    },
    {
        "appendix": "L8.1.1",
        "claim": "regime separation lift over base rate",
        "source": "results/level9_prep/context_separation_seed42.json",
        "expected": 0.2880,
        "compute": context_separation("lift_over_base_rate"),
    },
    {
        "appendix": "L8.1.1",
        "claim": "narrative identity lift is negative",
        "source": "results/level9_prep/context_separation_seed42.json",
        "expected": -0.1050,
        "compute": context_separation("narrative_lift_over_base_rate"),
    },
]


def main() -> int:
    """Recompute each claim and compare it to the recorded value."""
    parser = argparse.ArgumentParser(description="Recompute the paper's numbers.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for entry in CLAIMS:
        source = PROJECT_ROOT / entry["source"]
        if not source.is_file():
            rows.append(
                {
                    "seed": args.seed,
                    "appendix": entry["appendix"],
                    "claim": entry["claim"],
                    "source": entry["source"],
                    "expected": entry["expected"],
                    "actual": "source absent",
                    "matches": False,
                }
            )
            continue
        try:
            actual = entry["compute"]()
        except Exception as exc:
            rows.append(
                {
                    "seed": args.seed,
                    "appendix": entry["appendix"],
                    "claim": entry["claim"],
                    "source": entry["source"],
                    "expected": entry["expected"],
                    "actual": f"error: {exc}",
                    "matches": False,
                }
            )
            continue
        matches = abs(actual - entry["expected"]) <= TOLERANCE
        rows.append(
            {
                "seed": args.seed,
                "appendix": entry["appendix"],
                "claim": entry["claim"],
                "source": entry["source"],
                "expected": entry["expected"],
                "actual": round(actual, 6),
                "matches": matches,
            }
        )

    csv_path = OUT_DIR / f"numbers_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    matched = sum(1 for r in rows if r["matches"])
    (OUT_DIR / f"numbers_seed{args.seed}.json").write_text(
        json.dumps(
            {
                "seed": args.seed,
                "claims_checked": len(rows),
                "claims_matching": matched,
                "tolerance": TOLERANCE,
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    for row in rows:
        mark = "ok  " if row["matches"] else "DIFF"
        print(
            f"  {mark} {row['appendix']:<8} {str(row['expected']):>9} vs "
            f"{str(row['actual']):>9}  {row['claim'][:52]}"
        )
    print(f"  {matched} of {len(rows)} claims reproduce within {TOLERANCE}")
    return 0 if matched == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
