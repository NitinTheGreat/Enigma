"""
Module: scripts/level7_fit_threshold.py

Fits and validates the embedding scorer's similarity threshold.

How the scorer is evaluated. In use it is always asked about one specific
category: does this hypothesis describe the narrative this scenario expects.
The evaluation therefore mirrors that. Every labelled hypothesis is paired
with every one of the six categories, giving 300 decisions, and each is a
positive exactly when the hand label names that category. Precision and
recall are computed over those 300 decisions.

This is stricter and more honest than asking whether the closest narrative
clears the threshold. A hypothesis about benign automation may sit moderately
close to some attack narrative without describing it, and the paired
evaluation counts that as the false positive it would be in use.

An argmax variant is reported alongside, in which a category counts only when
it is the closest of all six. That rule was implemented first and is recorded
because it fails: benign systems prose sits close enough to several attack
narratives that requiring the expected one to win outright costs far more
recall than it buys precision.

The chosen threshold maximises the harmonic mean of precision and recall,
with ties broken towards the higher threshold because a stricter scorer fails
safe: it under credits rather than inventing matches.
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

from scenarios.semantic import CATEGORY_NARRATIVES, EmbeddingMatcher  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "scoring"


def keyword_prediction(text: str) -> str | None:
    """Return the category the original keyword scorer would assign."""
    from scenarios.generator import CATEGORIES

    lowered = text.lower()
    for category in CATEGORIES:
        if any(keyword.lower() in lowered for keyword in category.keywords):
            return category.name
    return None


def main() -> int:
    """Sweep the threshold, pick one, and report the validation."""
    parser = argparse.ArgumentParser(description="Fit the embedding threshold.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minimum", type=float, default=0.7)
    args = parser.parse_args()

    labels_path = RESULTS_DIR / f"hand_labels_seed{args.seed}.jsonl"
    rows = [
        json.loads(line)
        for line in labels_path.read_text(encoding="utf-8").splitlines()
        if line
    ]

    matcher = EmbeddingMatcher(threshold=0.0)
    provenance = matcher.provenance()

    scored: list[dict[str, Any]] = []
    for row in rows:
        assignment = matcher.assign(row["text"])
        scored.append(
            {
                "candidate_index": row["candidate_index"],
                "text": row["text"],
                "label": row["label"],
                "label_is_match": row["label_is_match"],
                "best_category": assignment.category,
                "best_similarity": assignment.similarity,
                "similarities": assignment.similarities,
                "keyword_prediction": keyword_prediction(row["text"]),
            }
        )

    categories = sorted(CATEGORY_NARRATIVES)
    sweep: list[dict[str, Any]] = []
    for step in range(15, 81):
        threshold = step / 100.0
        tp = fp = fn = tn = 0
        argmax_tp = argmax_fp = argmax_fn = 0
        for item in scored:
            best_name = max(item["similarities"], key=item["similarities"].get)
            for category in categories:
                similarity = item["similarities"][category]
                actual = item["label"] == category
                predicted = similarity >= threshold
                if predicted and actual:
                    tp += 1
                elif predicted and not actual:
                    fp += 1
                elif not predicted and actual:
                    fn += 1
                else:
                    tn += 1

                argmax_predicted = predicted and category == best_name
                if argmax_predicted and actual:
                    argmax_tp += 1
                elif argmax_predicted and not actual:
                    argmax_fp += 1
                elif not argmax_predicted and actual:
                    argmax_fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        sweep.append(
            {
                "seed": args.seed,
                "threshold": round(threshold, 2),
                "decisions": len(scored) * len(categories),
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": tn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "argmax_precision": round(argmax_tp / (argmax_tp + argmax_fp), 4)
                if (argmax_tp + argmax_fp)
                else 0.0,
                "argmax_recall": round(argmax_tp / (argmax_tp + argmax_fn), 4)
                if (argmax_tp + argmax_fn)
                else 0.0,
            }
        )

    best = max(sweep, key=lambda r: (r["f1"], r["threshold"]))

    keyword_tp = keyword_fp = keyword_fn = 0
    for item in scored:
        for category in categories:
            actual = item["label"] == category
            predicted = item["keyword_prediction"] == category
            if predicted and actual:
                keyword_tp += 1
            elif predicted and not actual:
                keyword_fp += 1
            elif not predicted and actual:
                keyword_fn += 1
    keyword_exact = sum(
        1 for i in scored if (i["keyword_prediction"] or "none") == i["label"]
    )
    keyword_precision = (
        keyword_tp / (keyword_tp + keyword_fp) if (keyword_tp + keyword_fp) else 0.0
    )
    keyword_recall = (
        keyword_tp / (keyword_tp + keyword_fn) if (keyword_tp + keyword_fn) else 0.0
    )

    passes = best["precision"] >= args.minimum and best["recall"] >= args.minimum

    report = {
        "seed": args.seed,
        "provenance": provenance,
        "labelled_items": len(scored),
        "positives": sum(1 for i in scored if i["label_is_match"]),
        "negatives": sum(1 for i in scored if not i["label_is_match"]),
        "labelled_categories_present": sorted(
            {i["label"] for i in scored if i["label_is_match"]}
        ),
        "categories_defined": sorted(CATEGORY_NARRATIVES),
        "chosen_threshold": best["threshold"],
        "chosen": best,
        "minimum_required": args.minimum,
        "passes_minimum": passes,
        "keyword_baseline": {
            "precision": round(keyword_precision, 4),
            "recall": round(keyword_recall, 4),
            "exact_category_accuracy": round(keyword_exact / len(scored), 4),
            "true_positive": keyword_tp,
            "false_positive": keyword_fp,
            "false_negative": keyword_fn,
        },
        "sweep": sweep,
    }
    (RESULTS_DIR / f"threshold_fit_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    with (RESULTS_DIR / f"threshold_sweep_seed{args.seed}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sweep[0].keys()))
        writer.writeheader()
        writer.writerows(sweep)

    with (RESULTS_DIR / f"label_scores_seed{args.seed}.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for item in scored:
            handle.write(json.dumps(item, separators=(",", ":")) + "\n")

    print(f"seed {args.seed}")
    print(f"model {provenance['model_name']}")
    print(
        f"sentence-transformers {provenance['sentence_transformers_version']}  "
        f"torch {provenance['torch_version']}  "
        f"narratives {provenance['narratives_hash']}"
    )
    print(
        f"labelled {len(scored)}  positives {report['positives']}  "
        f"negatives {report['negatives']}"
    )
    print(f"labelled categories present {report['labelled_categories_present']}")
    print()
    header = f"{'thresh':>7}{'TP':>5}{'FP':>5}{'FN':>5}{'TN':>5}{'prec':>8}{'recall':>8}{'F1':>8}{'argmaxR':>8}"
    print(header)
    print("-" * len(header))
    for row in sweep:
        if round(row["threshold"] * 100) % 5:
            continue
        print(
            f"{row['threshold']:>7}{row['true_positive']:>5}{row['false_positive']:>5}"
            f"{row['false_negative']:>5}{row['true_negative']:>5}"
            f"{row['precision']:>8}{row['recall']:>8}{row['f1']:>8}"
            f"{row['argmax_recall']:>8}"
        )
    print()
    print(f"chosen threshold {best['threshold']}")
    print(
        f"  precision {best['precision']}  recall {best['recall']}  "
        f"F1 {best['f1']}"
    )
    print(
        f"keyword baseline on the same labels  precision {keyword_precision:.4f}  "
        f"recall {keyword_recall:.4f}  exact {keyword_exact / len(scored):.4f}"
    )
    print()
    if passes:
        print(f"PASS both precision and recall are at or above {args.minimum}")
    else:
        print(f"FAIL precision or recall is below {args.minimum}")
    return 0 if passes else 2


if __name__ == "__main__":
    raise SystemExit(main())
