"""
Module: scripts/level10_calibrate_matcher.py

Calibrates the hypothesis identity matcher before the repair experiment runs.

What this matcher is for, and what it is not. L9 established that generation
replaces the hypothesis list every iteration, so no named hypothesis survives
and dominant_iterations never leaves zero. The repair gives a new hypothesis
the identity of the prior one it continues, which is a matching problem
*within a single analysis*, between consecutive iterations of the same
reasoning loop.

That is a different job from the scorer rejected in L7.9. That scorer tried
to decide whether a free text hypothesis matched a ground truth narrative,
across a six way catalogue the context carries no signal about. This one asks
whether two pieces of text produced seconds apart by the same model about the
same situation are the same hypothesis restated. The second question is far
easier and its failure mode is visible: a loose rule merges distinct
hypotheses, which the spot check in the repair experiment is there to catch.

How the threshold is chosen. Pairs are drawn from the Level 9 logs: within
analysis pairs are hypotheses from consecutive iterations of the same
analysis, which is where a genuine continuation would be found, and across
analysis pairs come from different situations entirely, which are almost
never the same hypothesis. A threshold that separates those two
distributions is the one to use, and it is written here and read by the
repair rather than chosen afterwards.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean, median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
RESULTS_DIR = PROJECT_ROOT / "results" / "repair"

WORD = re.compile(r"[^a-z0-9]+")


def normalise(text: str) -> str:
    """Lowercase, strip punctuation to spaces, collapse whitespace."""
    return " ".join(WORD.sub(" ", str(text).lower()).split())


def similarity(left: str, right: str) -> float:
    """Return the normalised text similarity of two hypotheses."""
    return SequenceMatcher(None, normalise(left), normalise(right)).ratio()


def main() -> int:
    """Measure the two similarity distributions and pick a threshold."""
    parser = argparse.ArgumentParser(description="Calibrate the identity matcher.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cell", type=str, default="allon_t080_42")
    parser.add_argument("--max-analyses", type=int, default=120)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    log = ABLATION_DIR / f"{args.cell}.jsonl"
    descriptions_path = ABLATION_DIR / f"{args.cell}_descriptions.json"
    if not (log.exists() and descriptions_path.exists()):
        print(f"missing inputs for cell {args.cell}")
        return 1
    descriptions = json.loads(descriptions_path.read_text(encoding="utf-8"))

    by_situation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        by_situation[str(record.get("situation_id"))].append(record)

    analyses: list[list[dict[str, Any]]] = []
    for records in by_situation.values():
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        index = -1
        previous = 99
        for record in records:
            iteration = int(record.get("iteration") or 0)
            if iteration <= previous:
                index += 1
            previous = iteration
            grouped[index].append(record)
        for analysis in grouped.values():
            if len(analysis) >= 2:
                analyses.append(analysis)
    analyses = analyses[: args.max_analyses]

    def texts_at(analysis: list[dict[str, Any]], iteration: int) -> list[str]:
        """Return the named hypothesis texts at one iteration."""
        out: list[str] = []
        for record in analysis:
            if int(record.get("iteration") or 0) != iteration:
                continue
            for hypothesis in record.get("hypotheses", []):
                if hypothesis.get("is_unknown"):
                    continue
                text = descriptions.get(str(hypothesis.get("text_hash")))
                if text:
                    out.append(text)
        return out

    within: list[float] = []
    for analysis in analyses:
        iterations = sorted({int(r.get("iteration") or 0) for r in analysis})
        for first, second in zip(iterations, iterations[1:]):
            left = texts_at(analysis, first)
            right = texts_at(analysis, second)
            for a in left:
                for b in right:
                    within.append(similarity(a, b))

    across: list[float] = []
    pool = [texts_at(a, sorted({int(r.get("iteration") or 0) for r in a})[0]) for a in analyses]
    for index in range(0, min(len(pool) - 1, 80)):
        for a in pool[index]:
            for b in pool[index + 1]:
                across.append(similarity(a, b))

    def spread(values: list[float]) -> dict[str, float]:
        """Return a compact description of a similarity distribution."""
        ordered = sorted(values)
        if not ordered:
            return {}
        def percentile(p: float) -> float:
            return ordered[min(len(ordered) - 1, int(p * len(ordered)))]
        return {
            "n": len(ordered),
            "min": round(ordered[0], 4),
            "p05": round(percentile(0.05), 4),
            "p25": round(percentile(0.25), 4),
            "median": round(median(ordered), 4),
            "mean": round(mean(ordered), 4),
            "p75": round(percentile(0.75), 4),
            "p95": round(percentile(0.95), 4),
            "max": round(ordered[-1], 4),
        }

    within_spread = spread(within)
    across_spread = spread(across)

    grid: list[dict[str, Any]] = []
    for step in range(30, 96, 5):
        threshold = step / 100.0
        kept = sum(1 for v in within if v >= threshold)
        leaked = sum(1 for v in across if v >= threshold)
        grid.append(
            {
                "seed": args.seed,
                "threshold": round(threshold, 2),
                "within_analysis_pairs_at_or_above": kept,
                "within_analysis_share": round(kept / len(within), 4) if within else 0.0,
                "across_analysis_pairs_at_or_above": leaked,
                "across_analysis_share": round(leaked / len(across), 4) if across else 0.0,
            }
        )

    chosen = None
    for row in grid:
        if row["across_analysis_share"] <= 0.01:
            chosen = row
            break

    report = {
        "seed": args.seed,
        "cell": args.cell,
        "analyses_examined": len(analyses),
        "rule": (
            "normalise to lowercase alphanumeric words, then difflib "
            "SequenceMatcher ratio, greedy one to one assignment in "
            "descending similarity, UNKNOWN excluded"
        ),
        "within_analysis_similarity": within_spread,
        "across_analysis_similarity": across_spread,
        "threshold_grid": grid,
        "chosen_threshold": chosen["threshold"] if chosen else None,
        "chosen_rationale": (
            "lowest threshold at which at most one per cent of across analysis "
            "pairs would be matched, chosen before the repair was run"
        ),
    }
    (RESULTS_DIR / f"matcher_calibration_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    csv_path = RESULTS_DIR / f"matcher_calibration_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(grid[0].keys()))
        writer.writeheader()
        writer.writerows(grid)

    print(f"seed {args.seed}   cell {args.cell}   analyses {len(analyses)}")
    print(f"rule: {report['rule']}")
    print()
    print(f"within analysis pairs  {json.dumps(within_spread)}")
    print(f"across analysis pairs  {json.dumps(across_spread)}")
    print()
    print(f"{'threshold':>10}{'within kept':>14}{'within share':>15}{'across share':>15}")
    print("-" * 54)
    for row in grid:
        print(
            f"{row['threshold']:>10}{row['within_analysis_pairs_at_or_above']:>14}"
            f"{row['within_analysis_share']:>15}{row['across_analysis_share']:>15}"
        )
    print()
    print(f"CHOSEN THRESHOLD {report['chosen_threshold']}")
    print(f"  {report['chosen_rationale']}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
