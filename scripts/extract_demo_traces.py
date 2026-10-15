"""
Module: scripts/extract_demo_traces.py

Extracts one logged reasoning trace per evidence regime into a small file
that is committed, so the demo can be built from committed results alone.

The full Level 9 run logs are gitignored because they run to a gigabyte, so
a trace cannot be read from a clean checkout. This script reads the local log
once and writes only the four analyses the demo replays, which is the same
arrangement as the Figure 3 trajectory extract. Nothing is typed in by hand:
every confidence, identifier and score below is copied from the log.

Selection rule, identical to the paper's Figure 3 and fixed before looking:
for each regime, among the situations of the all-on cell at seed 42 and
threshold 0.80, take the one whose evidence count at its first terminated
analysis is the median for that regime, ties broken by the smallest
situation identifier. For the unknown attack regime this must reproduce the
paper's situation, 09e0a866, and the script stops if it does not.

The trace replayed is that first terminated analysis, from its first
iteration to the record that ends it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from level7_label_extract import texts_from_cache  # noqa: E402

ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
SUITE = PROJECT_ROOT / "results" / "scenarios" / "sub_suite.jsonl"
OUT_DIR = PROJECT_ROOT / "results" / "demo"

REGIMES = ("clear", "ambiguous", "sparse", "unknown_attack")
PAPER_FIGURE_SITUATION = "09e0a866"


def scenario_of(entity: str) -> str | None:
    """Return the scenario identifier embedded in an entity name."""
    for part in entity.replace(":", "-").split("-"):
        if len(part) == 6 and part.startswith("s") and part[1:].isdigit():
            return part
    return None


def main() -> int:
    """Extract the four traces and write them to a committed file."""
    parser = argparse.ArgumentParser(description="Extract demo traces.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold", type=float, default=0.80)
    args = parser.parse_args()

    tag = "t%03d" % round(args.threshold * 100)
    log = ABLATION_DIR / ("allon_%s_%d.jsonl" % (tag, args.seed))
    entities_path = ABLATION_DIR / ("allon_%s_%d_entities.json" % (tag, args.seed))
    cache_path = ABLATION_DIR / ("cache_seed%d.json" % args.seed)
    for needed in (log, entities_path, SUITE):
        if not needed.is_file():
            print("missing input: %s" % needed.relative_to(PROJECT_ROOT))
            return 1

    truth: dict[str, dict[str, Any]] = {}
    for line in SUITE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            truth[row["scenario_id"]] = row["ground_truth"]
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    texts = texts_from_cache(cache_path) if cache_path.is_file() else {}

    records_by_situation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        records_by_situation[str(record["situation_id"])].append(record)

    first_analysis: dict[str, list[dict[str, Any]]] = {}
    for situation, records in records_by_situation.items():
        analysis: list[dict[str, Any]] = []
        for record in records:
            if int(record.get("iteration") or 0) == 1:
                analysis = []
            analysis.append(record)
            if record.get("terminated"):
                first_analysis[situation] = analysis
                break

    candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for situation, analysis in first_analysis.items():
        scenario = scenario_of(entities.get(situation, ""))
        if scenario is None or scenario not in truth:
            continue
        candidates[truth[scenario]["regime"]].append(
            (int(analysis[-1].get("evidence_count") or 0), situation)
        )

    traces = []
    for regime in REGIMES:
        pool = candidates.get(regime, [])
        if not pool:
            print("no situation found for regime %s" % regime)
            return 1
        counts = sorted(c for c, _ in pool)
        median = counts[len(counts) // 2]
        situation = sorted(s for c, s in pool if c == median)[0]
        analysis = first_analysis[situation]
        scenario = scenario_of(entities[situation])
        regime_truth = truth[scenario]
        final = analysis[-1]
        abstained = final.get("dominant_hypothesis_id") in (None, "UNKNOWN")
        iterations = []
        for record in analysis:
            named = []
            unknown_confidence = None
            for h in record.get("hypotheses", []):
                if h.get("is_unknown"):
                    unknown_confidence = h.get("confidence")
                    continue
                named.append({
                    "id": h.get("hypothesis_id"),
                    "confidence": h.get("confidence"),
                    "status": h.get("status"),
                    "text": texts.get(str(h.get("text_hash")), ""),
                })
            iterations.append({
                "iteration": record.get("iteration"),
                "evidence_count": record.get("evidence_count"),
                "unknown_confidence": unknown_confidence,
                "convergence_score": record.get("convergence_score"),
                "dominant_hypothesis_id": record.get("dominant_hypothesis_id"),
                "dominant_iterations": record.get("dominant_iterations"),
                "terminated": record.get("terminated"),
                "termination_reason": record.get("termination_reason"),
                "hypotheses": named,
            })
        traces.append({
            "regime": regime,
            "situation_id": situation,
            "scenario_id": scenario,
            "evidence_count_at_end": median,
            "regime_candidates": len(pool),
            "should_conclude": bool(regime_truth.get("should_conclude")),
            "verdict": "abstained" if abstained else "concluded",
            "right_call": abstained != bool(regime_truth.get("should_conclude")),
            "termination_reason": final.get("termination_reason"),
            "iterations": iterations,
        })

    unknown = next(t for t in traces if t["regime"] == "unknown_attack")
    if not unknown["situation_id"].startswith(PAPER_FIGURE_SITUATION):
        print("selection rule disagrees with the paper: unknown attack chose %s, paper has %s"
              % (unknown["situation_id"], PAPER_FIGURE_SITUATION))
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ("traces_seed%d_%s.json" % (args.seed, tag))
    out.write_text(json.dumps({
        "seed": args.seed,
        "threshold": args.threshold,
        "source_log": str(log.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "rule": "median evidence count at the first terminated analysis, per regime, "
                "ties broken by smallest situation id; matches paper Figure 3",
        "abstained_means": "UNKNOWN leads at the final record, as in scenarios/scoring.py",
        "traces": traces,
    }, indent=2), encoding="utf-8")

    print("seed %d   threshold %.2f   source %s" % (args.seed, args.threshold, log.name))
    for t in traces:
        print("  %-15s %s  evidence %-3d iterations %d  %-9s right call %-5s  (%d candidates)" % (
            t["regime"], t["situation_id"][:8], t["evidence_count_at_end"], len(t["iterations"]),
            t["verdict"], t["right_call"], t["regime_candidates"]))
    print("unknown attack matches paper Figure 3 situation %s" % PAPER_FIGURE_SITUATION)
    print("written %s" % out.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
