"""
Module: scripts/level10_repair_analyse.py

Compares the repaired run against its Level 9 baseline.

The baseline is the all on cell at the same threshold and seed, already in
results/ablation, and is not re-run. The two arms differ in exactly one
thing: whether a newly generated hypothesis inherits the identity of the
prior one it restates.

The question is whether persistence begins gating convergence once identity
is stable. Three outcomes are possible and all are reportable: the mechanism
was correctly specified and incorrectly coupled, it gates but rarely, or the
clamp blocks convergence regardless of identity.

Thirty matched pairs are written out for a by eye spot check, because a
matching rule that is too loose would merge distinct hypotheses and
manufacture persistence that the system has not earned.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scenarios.scoring import score_run  # noqa: E402

from level7_label_extract import texts_from_cache  # noqa: E402
from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
RESULTS_DIR = PROJECT_ROOT / "results" / "repair"

LIVE_METRICS = (
    "abstention_rate",
    "appropriate_abstention_rate",
    "inappropriate_abstention_rate",
    "premature_convergence_rate",
)


def threshold_tag(threshold: float) -> str:
    """Return the filename fragment for a threshold."""
    return f"t{int(round(threshold * 100)):03d}"


def split_analyses(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group a situation's records into separate analyses by iteration reset."""
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    index = -1
    previous = 99
    for record in records:
        iteration = int(record.get("iteration") or 0)
        if iteration <= previous:
            index += 1
        previous = iteration
        grouped[index].append(record)
    return list(grouped.values())


def inspect(path: Path) -> dict[str, Any]:
    """Measure identity recurrence, dominant iterations and convergence."""
    by_situation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        by_situation[str(record.get("situation_id"))].append(record)

    named_total = 0
    named_recurring = 0
    dominant_counter: Counter[int] = Counter()
    reasons: Counter[str] = Counter()
    terminal = 0
    iterations_final: list[int] = []
    scores: list[float] = []
    pairs: list[dict[str, Any]] = []

    for situation, records in by_situation.items():
        for analysis in split_analyses(records):
            if len(analysis) < 2:
                continue
            appearances: dict[str, dict[int, str]] = defaultdict(dict)
            for record in analysis:
                iteration = int(record.get("iteration") or 0)
                scores.append(float(record.get("convergence_score") or 0.0))
                for hypothesis in record.get("hypotheses", []):
                    if hypothesis.get("is_unknown"):
                        continue
                    key = str(hypothesis.get("hypothesis_id"))
                    appearances[key][iteration] = str(hypothesis.get("text_hash"))
                if record.get("terminated"):
                    terminal += 1
                    reasons[str(record.get("termination_reason"))] += 1
                    iterations_final.append(iteration)
                    dominant_counter[int(record.get("dominant_iterations") or 0)] += 1
            for key, seen in appearances.items():
                named_total += 1
                if len(seen) > 1:
                    named_recurring += 1
                    ordered = sorted(seen.items())
                    pairs.append(
                        {
                            "situation_id": situation,
                            "hypothesis_id": key,
                            "iterations": [i for i, _ in ordered],
                            "text_hashes": [h for _, h in ordered],
                        }
                    )

    return {
        "named_hypotheses": named_total,
        "named_recurring": named_recurring,
        "recurrence_rate": round(named_recurring / named_total, 4) if named_total else 0.0,
        "dominant_iterations_distribution": dict(sorted(dominant_counter.items())),
        "analyses_terminated": terminal,
        "termination_reasons": dict(reasons),
        "mean_iterations_to_termination": round(mean(iterations_final), 4)
        if iterations_final
        else 0.0,
        "max_convergence": round(max(scores), 4) if scores else 0.0,
        "matched_pairs": pairs,
    }


def main() -> int:
    """Compare every repaired cell against its baseline."""
    parser = argparse.ArgumentParser(description="Level 10 repair analysis.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--thresholds", type=str, default="0.30,0.50,0.80")
    parser.add_argument("--spot-check", type=int, default=30)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    thresholds = [float(t) for t in args.thresholds.split(",") if t.strip()]

    cache_texts: dict[str, str] = {}
    for cache_path in sorted(RESULTS_DIR.glob("cache_seed*.json")):
        cache_texts.update(texts_from_cache(cache_path))

    rows: list[dict[str, Any]] = []
    all_pairs: list[dict[str, Any]] = []
    descriptions_by_cell: dict[tuple[float, int], dict[str, str]] = {}

    for threshold, seed in product(thresholds, seeds):
        tag = threshold_tag(threshold)
        repair_log = RESULTS_DIR / f"repair_{tag}_{seed}_full.jsonl"
        baseline_log = ABLATION_DIR / f"allon_{tag}_{seed}.jsonl"
        if not (repair_log.exists() and baseline_log.exists()):
            continue

        repair_entities = json.loads(
            (RESULTS_DIR / f"repair_{tag}_{seed}_full_entities.json").read_text(
                encoding="utf-8"
            )
        )
        repair_descriptions = json.loads(
            (RESULTS_DIR / f"repair_{tag}_{seed}_full_descriptions.json").read_text(
                encoding="utf-8"
            )
        )
        merged = dict(cache_texts)
        merged.update(repair_descriptions)
        descriptions_by_cell[(threshold, seed)] = merged
        baseline_entities = json.loads(
            (ABLATION_DIR / f"allon_{tag}_{seed}_entities.json").read_text(
                encoding="utf-8"
            )
        )
        baseline_descriptions_path = ABLATION_DIR / f"allon_{tag}_{seed}_descriptions.json"
        baseline_descriptions = (
            json.loads(baseline_descriptions_path.read_text(encoding="utf-8"))
            if baseline_descriptions_path.exists()
            else {}
        )

        for arm, log, ents, descs in (
            ("repair", repair_log, repair_entities, repair_descriptions),
            ("baseline", baseline_log, baseline_entities, baseline_descriptions),
        ):
            stats = inspect(log)
            _, overall, per_regime = score_run(log, scenarios, ents, descs)
            row: dict[str, Any] = {
                "seed": seed,
                "convergence_threshold": threshold,
                "arm": arm,
                "situations_scored": overall.situations,
                "named_hypotheses": stats["named_hypotheses"],
                "named_recurring": stats["named_recurring"],
                "recurrence_rate": stats["recurrence_rate"],
                "max_dominant_iterations": max(
                    stats["dominant_iterations_distribution"] or {0: 0}
                ),
                "analyses_terminated": stats["analyses_terminated"],
                "converged": stats["termination_reasons"].get("converged", 0),
                "convergence_fraction": round(
                    stats["termination_reasons"].get("converged", 0)
                    / stats["analyses_terminated"],
                    4,
                )
                if stats["analyses_terminated"]
                else 0.0,
                "mean_iterations_to_termination": stats["mean_iterations_to_termination"],
                "max_convergence": stats["max_convergence"],
                "dominant_iterations_distribution": json.dumps(
                    stats["dominant_iterations_distribution"]
                ),
            }
            for metric in LIVE_METRICS:
                row[metric] = getattr(overall, metric)
            for regime in ("sparse", "unknown_attack"):
                for metric in LIVE_METRICS:
                    row[f"{regime}_{metric}"] = per_regime[regime].to_dict()[metric]
            rows.append(row)
            if arm == "repair":
                for pair in stats["matched_pairs"]:
                    pair["threshold"] = threshold
                    pair["seed"] = seed
                    all_pairs.append(pair)

    if not rows:
        print("no cells found")
        return 1

    csv_path = RESULTS_DIR / f"repair_cells_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    rng = random.Random(args.seed)
    sampled = rng.sample(all_pairs, min(args.spot_check, len(all_pairs)))
    spot: list[dict[str, Any]] = []
    for pair in sampled:
        descs = descriptions_by_cell.get((pair["threshold"], pair["seed"]), {})
        texts = [descs.get(h, "(text not recovered)") for h in pair["text_hashes"]]
        spot.append(
            {
                "seed": pair["seed"],
                "threshold": pair["threshold"],
                "situation_id": pair["situation_id"],
                "iterations": pair["iterations"],
                "texts": texts,
                "identical": len(set(texts)) == 1,
            }
        )
    spot_path = RESULTS_DIR / f"spot_check_seed{args.seed}.jsonl"
    with spot_path.open("w", encoding="utf-8") as handle:
        for entry in spot:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def summarise(arm: str, threshold: float, field: str) -> tuple[float, float]:
        """Return mean and deviation over seeds for one arm and threshold."""
        values = [
            float(r[field])
            for r in rows
            if r["arm"] == arm and r["convergence_threshold"] == threshold
        ]
        if not values:
            return 0.0, 0.0
        return mean(values), (pstdev(values) if len(values) > 1 else 0.0)

    summary: list[dict[str, Any]] = []
    for threshold in thresholds:
        entry: dict[str, Any] = {"seed": args.seed, "convergence_threshold": threshold}
        for arm in ("baseline", "repair"):
            for field in (
                "recurrence_rate",
                "max_dominant_iterations",
                "convergence_fraction",
                "mean_iterations_to_termination",
                "max_convergence",
                *LIVE_METRICS,
                "sparse_abstention_rate",
                "unknown_attack_abstention_rate",
            ):
                m, sd = summarise(arm, threshold, field)
                entry[f"{arm}_{field}_mean"] = round(m, 4)
                entry[f"{arm}_{field}_sd"] = round(sd, 4)
        summary.append(entry)

    summary_path = RESULTS_DIR / f"repair_summary_seed{args.seed}.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    gated = any(
        s["repair_convergence_fraction_mean"] > s["baseline_convergence_fraction_mean"]
        for s in summary
    )
    identity_fixed = any(
        s["repair_recurrence_rate_mean"] > s["baseline_recurrence_rate_mean"]
        for s in summary
    )
    if identity_fixed and gated:
        outcome = "correctly_specified_incorrectly_coupled"
    elif identity_fixed and not gated:
        outcome = "identity_fixed_but_clamp_still_blocks"
    else:
        outcome = "identity_not_fixed"

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "thresholds": thresholds,
        "seeds": seeds,
        "cells": rows,
        "summary": summary,
        "spot_check_sampled": len(spot),
        "spot_check_identical_text": sum(1 for s in spot if s["identical"]),
        "outcome": outcome,
    }
    (RESULTS_DIR / f"repair_analysis_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(f"seed {args.seed}   cells {len(rows)}   matched pairs {len(all_pairs)}")
    print()
    header = (
        f"{'threshold':>10}{'arm':>10}{'recurrence':>12}{'maxDomIt':>10}"
        f"{'convFrac':>10}{'meanIters':>11}{'maxConv':>9}"
    )
    print(header)
    print("-" * len(header))
    for s in summary:
        for arm in ("baseline", "repair"):
            print(
                f"{s['convergence_threshold']:>10}{arm:>10}"
                f"{s[f'{arm}_recurrence_rate_mean']:>12.4f}"
                f"{s[f'{arm}_max_dominant_iterations_mean']:>10.2f}"
                f"{s[f'{arm}_convergence_fraction_mean']:>10.4f}"
                f"{s[f'{arm}_mean_iterations_to_termination_mean']:>11.4f}"
                f"{s[f'{arm}_max_convergence_mean']:>9.4f}"
            )
    print()
    print(f"OUTCOME {outcome}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"written {summary_path.relative_to(PROJECT_ROOT)}")
    print(f"written {spot_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
