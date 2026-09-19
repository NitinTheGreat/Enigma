"""
Module: scripts/level7_compare.py

Assembles the outcome metric comparison across every model path that has run.

Columns. fallback and mock are the two substitutes reported in L7.4. real is
the path restored in this work. The original 7 August smoke is carried as a
fourth column wherever it can be, which is only the quantities derivable from
its run log: it was written without a summary, a manifest or the scenario to
situation mapping and the hypothesis texts that scoring needs, so its eight
outcome metrics cannot be recovered. That is not a limitation of this script.
It is the reason the smoke had to be run again.

Sample sizes differ between columns and are printed with them. The fallback
and mock columns cover the full 625 situation suite. The real column covers
the declared stratified slice it was run on. A rate from one is not a rate
from the other and the table says so rather than inviting the comparison.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.graph.nodes import _fallback_hypotheses  # noqa: E402
from enigma_reason.observability.run_log import text_hash  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "budget"

METRIC_NAMES = (
    "correct_conclusion_rate",
    "false_conclusion_rate",
    "abstention_rate",
    "appropriate_abstention_rate",
    "inappropriate_abstention_rate",
    "premature_convergence_rate",
    "single_iteration_conclusion_rate",
    "mean_iterations_to_termination",
)


def log_derived(path: Path) -> dict[str, Any]:
    """Return the quantities a bare run log can support without scoring."""
    if not path.is_file():
        return {}
    fallback_hashes = {text_hash(e["description"]) for e in _fallback_hypotheses()}
    scores: list[float] = []
    situations: set[str] = set()
    texts: set[str] = set()
    reasons: dict[str, int] = {}
    fallback_iterations = 0
    unknown_dominant = 0
    terminal = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        situations.add(str(record.get("situation_id")))
        scores.append(float(record.get("convergence_score", 0.0)))
        hypotheses = record.get("hypotheses", [])
        if any(h.get("text_hash") in fallback_hashes for h in hypotheses):
            fallback_iterations += 1
        for hypothesis in hypotheses:
            if not hypothesis.get("is_unknown"):
                texts.add(str(hypothesis.get("text_hash")))
        if record.get("terminated"):
            terminal += 1
            reason = str(record.get("termination_reason", "unknown"))
            reasons[reason] = reasons.get(reason, 0) + 1
            if hypotheses:
                leader = max(hypotheses, key=lambda h: h.get("confidence", 0.0))
                if leader.get("is_unknown"):
                    unknown_dominant += 1
    return {
        "iterations": len(scores),
        "situations": len(situations),
        "distinct_hypothesis_hashes": len(texts),
        "max_convergence": round(max(scores), 4) if scores else 0.0,
        "mean_convergence": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "termination_reasons": reasons,
        "unknown_dominant_fraction": round(unknown_dominant / terminal, 4)
        if terminal
        else 0.0,
        "fallback_iterations": fallback_iterations,
        "fallback_iteration_fraction": round(fallback_iterations / len(scores), 4)
        if scores
        else 0.0,
    }


def load_report(tag: str) -> dict[str, Any]:
    """Read one scored run report if it exists."""
    path = SCENARIOS_DIR / f"validation_run_{tag}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    """Print and write the comparison across model paths."""
    parser = argparse.ArgumentParser(description="Level 7 model path comparison.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        ("fallback", load_report("fallback")),
        ("mock", load_report("mock")),
        ("real", load_report("real")),
    ]
    smoke = log_derived(SCENARIOS_DIR / "validation_run_log_real_smoke.jsonl")

    rows: list[dict[str, Any]] = []
    for metric in METRIC_NAMES:
        row: dict[str, Any] = {"seed": args.seed, "metric": metric}
        for name, report in columns:
            overall = report.get("overall", {})
            row[name] = overall.get(metric, "")
        row["real_smoke_7aug"] = "not recoverable"
        rows.append(row)

    csv_path = RESULTS_DIR / f"model_path_comparison_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    width = 38
    print(f"seed {args.seed}")
    print()
    header = f"{'metric':<{width}}{'fallback':>12}{'mock':>12}{'real':>12}{'smoke':>16}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['metric']:<{width}}{str(row['fallback']):>12}"
            f"{str(row['mock']):>12}{str(row['real']):>12}"
            f"{row['real_smoke_7aug']:>16}"
        )
    print()

    print(f"{'situations scored':<{width}}", end="")
    for name, report in columns:
        print(f"{str(report.get('situations_scored', '')):>12}", end="")
    print(f"{smoke.get('situations', ''):>16}")

    print(f"{'analyses':<{width}}", end="")
    for name, report in columns:
        print(f"{str(report.get('analyses_run', '')):>12}", end="")
    print(f"{'':>16}")

    print(f"{'distinct hypothesis texts':<{width}}", end="")
    for name, report in columns:
        print(f"{str(report.get('distinct_hypothesis_texts', '')):>12}", end="")
    print(f"{smoke.get('distinct_hypothesis_hashes', ''):>16}")

    print(f"{'max convergence':<{width}}", end="")
    for name, report in columns:
        print(f"{str(report.get('convergence', {}).get('max_convergence', '')):>12}", end="")
    print(f"{smoke.get('max_convergence', ''):>16}")

    print(f"{'fallback iteration fraction':<{width}}", end="")
    for name, report in columns:
        print(f"{'':>12}", end="")
    print(f"{smoke.get('fallback_iteration_fraction', ''):>16}")

    report_path = RESULTS_DIR / f"model_path_comparison_seed{args.seed}.json"
    report_path.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "metrics": rows,
                "real_smoke_log_derived": smoke,
                "scored_runs": {
                    name: {
                        "situations_scored": report.get("situations_scored"),
                        "analyses_run": report.get("analyses_run"),
                        "llm": report.get("llm"),
                        "suite": report.get("suite"),
                        "convergence": report.get("convergence"),
                        "cache": report.get("cache"),
                        "seconds_per_model_call": report.get("seconds_per_model_call"),
                    }
                    for name, report in columns
                    if report
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print()
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"written {report_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
