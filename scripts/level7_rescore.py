"""
Module: scripts/level7_rescore.py

Re-scores an existing run log under both scorers without calling the model.

Scoring needs three things the run log does not carry: the hypothesis texts
behind its hashes, which are rebuilt from the response cache written by the
same run; the scenario each situation belongs to, which is recovered from the
run's outcomes file; and the frozen suite, which supplies the ground truth.
With those in hand a log can be scored again under a different matcher, so
the two scorers are compared on identical reasoning rather than on two runs
that would differ for unrelated reasons.

This is what makes the L7.9 comparison honest. Neither column re-runs the
model, so any difference between them is the scorer and nothing else.
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
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scenarios.scoring import score_run  # noqa: E402

from level7_label_extract import texts_from_cache  # noqa: E402
from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "scoring"

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


def main() -> int:
    """Score one run log under the keyword and embedding matchers."""
    parser = argparse.ArgumentParser(description="Re-score a run log.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--log", type=str, default=str(SCENARIOS_DIR / "validation_run_log_real.jsonl")
    )
    parser.add_argument(
        "--cache", type=str, default=str(SCENARIOS_DIR / "gemini_cache_real.json")
    )
    parser.add_argument(
        "--outcomes",
        type=str,
        default=str(SCENARIOS_DIR / "validation_outcomes_real.jsonl"),
    )
    parser.add_argument("--suite", type=str, default=str(SCENARIOS_DIR / "suite.jsonl"))
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    scenarios = load_suite(Path(args.suite))
    descriptions = texts_from_cache(Path(args.cache))

    situation_entities: dict[str, str] = {}
    for line in Path(args.outcomes).read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        situation_entities[row["situation_id"]] = f"rescore-{row['scenario_id']}"

    from scenarios.semantic import EmbeddingMatcher

    embedding = EmbeddingMatcher()

    results: dict[str, Any] = {}
    for name, matcher in (("keyword", None), ("embedding", embedding)):
        outcomes, overall, per_regime = score_run(
            Path(args.log), scenarios, situation_entities, descriptions, matcher
        )
        results[name] = {
            "overall": overall.to_dict(),
            "per_regime": {k: v.to_dict() for k, v in per_regime.items()},
            "situations": overall.situations,
            "outcomes": [o.to_dict() for o in outcomes],
        }

    rows = []
    for metric in METRIC_NAMES:
        keyword_value = results["keyword"]["overall"][metric]
        embedding_value = results["embedding"]["overall"][metric]
        rows.append(
            {
                "seed": args.seed,
                "metric": metric,
                "keyword": keyword_value,
                "embedding": embedding_value,
                "changed": keyword_value != embedding_value,
            }
        )

    csv_path = RESULTS_DIR / f"rescore_comparison_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "seed": args.seed,
        "log": str(Path(args.log).name),
        "situations_scored": results["keyword"]["situations"],
        "scorers": {
            "keyword": "validated, precision 0.8125 recall 0.8125 on the hand labels",
            "embedding": (
                "REJECTED, precision 0.2917 recall 0.4375 on the hand labels, "
                "shown for the record only"
            ),
        },
        "embedding_provenance": embedding.provenance(),
        "metrics": rows,
        "keyword_overall": results["keyword"]["overall"],
        "embedding_overall": results["embedding"]["overall"],
        "keyword_per_regime": results["keyword"]["per_regime"],
        "embedding_per_regime": results["embedding"]["per_regime"],
    }
    json_path = RESULTS_DIR / f"rescore_comparison_seed{args.seed}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"seed {args.seed}   situations {results['keyword']['situations']}")
    print()
    header = f"{'metric':<36}{'keyword':>12}{'embedding':>12}{'changed':>10}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['metric']:<36}{str(row['keyword']):>12}"
            f"{str(row['embedding']):>12}{str(row['changed']):>10}"
        )
    print()
    changed = [r["metric"] for r in rows if r["changed"]]
    print(f"metrics that changed: {changed or 'none'}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"written {json_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
