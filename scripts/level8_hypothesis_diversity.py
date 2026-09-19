"""
Module: scripts/level8_hypothesis_diversity.py

Asks how many narratives the model actually proposes, across the whole study.

The question this answers. The seven situation slice in L7.9.2 produced
positive instances of exactly one of the six categories, and a sample that
small cannot distinguish a narrow model from a narrow sample. The clock study
produces sixty six situations at five seeds in three modes, which is enough
that a count still stuck at one or two is a property of the system rather
than of the sample.

Two competing explanations are separated rather than asserted. If the prompt
template steers the model toward one narrative family, the same narrow set of
categories will appear regardless of which regime the evidence came from. If
instead the regimes produce evidence signatures the model cannot tell apart,
the categories named will be narrow but will not correlate with regime. The
per regime breakdown distinguishes them.

Counting uses the keyword scorer, the validated one, applied to every
hypothesis text rather than only to the dominant one, because a narrative the
model proposed and then discarded still shows it was capable of proposing it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from enigma_reason.observability.run_log import text_hash  # noqa: E402
from scenarios.generator import CATEGORIES  # noqa: E402

from level7_label_extract import texts_from_cache  # noqa: E402
from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "clock_study"


def category_of(text: str) -> str | None:
    """Return the category the keyword scorer assigns to one hypothesis."""
    lowered = text.lower()
    for category in CATEGORIES:
        if any(keyword.lower() in lowered for keyword in category.keywords):
            return category.name
    return None


def main() -> int:
    """Count narratives named across the study and break them down by regime."""
    parser = argparse.ArgumentParser(description="Hypothesis diversity across Level 8.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--modes", type=str, default="conflated,wall,separated")
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    regime_of_scenario = {
        s.scenario_id: s.ground_truth.regime.value for s in scenarios
    }
    expected_of_scenario = {
        s.scenario_id: s.ground_truth.expected_conclusion for s in scenarios
    }

    texts: dict[str, str] = {}
    for seed in seeds:
        cache_path = RESULTS_DIR / f"cache_seed{seed}.json"
        if cache_path.is_file():
            texts.update(texts_from_cache(cache_path))

    entity_regime: dict[str, str] = {}
    for scenario in scenarios:
        for entity in scenario.entities:
            entity_regime[str(entity)] = scenario.ground_truth.regime.value

    named: Counter[str] = Counter()
    named_by_regime: dict[str, Counter[str]] = defaultdict(Counter)
    dominant_named: Counter[str] = Counter()
    hypotheses_seen = 0
    unresolved = 0
    distinct_texts: set[str] = set()

    situation_regime: dict[str, str] = {}
    situation_expected: dict[str, str] = {}
    for mode in modes:
        for seed in seeds:
            outcomes_path = RESULTS_DIR / f"outcomes_{mode}_{seed}.jsonl"
            if not outcomes_path.is_file():
                continue
            for line in outcomes_path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                row = json.loads(line)
                situation_regime[row["situation_id"]] = row["regime"]
                situation_expected[row["situation_id"]] = row["expected_conclusion"]

    for mode in modes:
        for seed in seeds:
            path = RESULTS_DIR / f"{mode}_{seed}.jsonl"
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                record = json.loads(line)
                if record.get("record_type") == "retry":
                    continue
                situation = str(record.get("situation_id"))
                leader = record.get("dominant_hypothesis_id")
                for hypothesis in record.get("hypotheses", []):
                    if hypothesis.get("is_unknown"):
                        continue
                    hypotheses_seen += 1
                    digest = str(hypothesis.get("text_hash"))
                    text = texts.get(digest)
                    if text is None:
                        unresolved += 1
                        continue
                    distinct_texts.add(text)
                    category = category_of(text)
                    if category:
                        named[category] += 1
                        regime = situation_regime.get(situation, "unmapped")
                        named_by_regime[regime][category] += 1
                        if hypothesis.get("hypothesis_id") == leader:
                            dominant_named[category] += 1

    all_categories = [c.name for c in CATEGORIES]
    report: dict[str, Any] = {
        "seed": args.seed,
        "seeds": seeds,
        "modes": modes,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "hypotheses_seen": hypotheses_seen,
        "hypotheses_unresolved": unresolved,
        "distinct_hypothesis_texts": len(distinct_texts),
        "categories_defined": all_categories,
        "categories_named": sorted(named),
        "categories_named_count": len(named),
        "categories_never_named": sorted(set(all_categories) - set(named)),
        "named_counts": dict(named.most_common()),
        "dominant_named_counts": dict(dominant_named.most_common()),
        "named_by_regime": {k: dict(v.most_common()) for k, v in named_by_regime.items()},
        "situations_mapped_to_regime": len(situation_regime),
        "reading": (
            "If the same narrow set of categories appears in every regime, the "
            "prompt template is steering the model. If the set is narrow but "
            "varies with regime, the regimes are distinguishable and the model "
            "is simply terse. If it is narrow and the regimes carry the same "
            "categories in the same proportions, the evidence signatures the "
            "generator produces do not separate."
        ),
        "unnamed_hypotheses": hypotheses_seen - unresolved - sum(named.values()),
    }
    (RESULTS_DIR / f"hypothesis_diversity_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    csv_path = RESULTS_DIR / f"hypothesis_diversity_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "category", "times_named", "times_dominant"])
        for category in all_categories:
            writer.writerow(
                [args.seed, category, named.get(category, 0), dominant_named.get(category, 0)]
            )

    print(f"seed {args.seed}   modes {modes}   seeds {seeds}")
    print(f"hypotheses examined      {hypotheses_seen}")
    print(f"unresolved text          {unresolved}")
    print(f"distinct hypothesis text {len(distinct_texts)}")
    print()
    print(f"{'category':<24}{'named':>8}{'dominant':>10}")
    print("-" * 42)
    for category in all_categories:
        print(f"{category:<24}{named.get(category, 0):>8}{dominant_named.get(category, 0):>10}")
    print()
    print(f"situations mapped      {len(situation_regime)}")
    print()
    print("named by regime")
    for regime in sorted(named_by_regime):
        print(f"  {regime:<16} {json.dumps(dict(named_by_regime[regime].most_common()))}")
    print()
    print(f"categories named       {len(named)} of {len(all_categories)}")
    print(f"never named            {report['categories_never_named']}")
    print(f"hypotheses naming none {report['unnamed_hypotheses']}")
    print()
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
