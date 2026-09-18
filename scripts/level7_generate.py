"""
Module: scripts/level7_generate.py

Generates and freezes the scenario suite.

Writes results/scenarios/suite.jsonl, results/scenarios/suite_manifest.json and
the entity correlation report that rules out the Level 5 artefact.

The artefact test is the reason this script does more than write a file. Level 5
assigned entities by index modulo sixteen, which is uncorrelated with anything,
so every situation was a uniform random sample of the corpus and grouping by
entity grouped nothing. The same statistic is computed here two ways, once on
this generator's entity assignment and once on a reconstruction of the Level 5
assignment over the identical signals, so the contrast is measured rather than
asserted.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from scenarios.generator import (  # noqa: E402
    Regime,
    Scenario,
    generate_suite,
    suite_hash,
)

RESULTS_DIR = PROJECT_ROOT / "results" / "scenarios"
LEVEL5_ENTITY_POOL = 16


def entropy(counts: Counter) -> float:
    """Return the Shannon entropy of a count distribution in bits."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    result = 0.0
    for value in counts.values():
        if value == 0:
            continue
        p = value / total
        result -= p * math.log2(p)
    return result


def cramers_v(pairs: list[tuple[str, str]]) -> float:
    """Return Cramer's V between two categorical variables.

    Implemented directly rather than pulled from a statistics package, because
    the agent environment deliberately carries no scientific stack.
    """
    if not pairs:
        return 0.0
    rows = sorted({a for a, _ in pairs})
    cols = sorted({b for _, b in pairs})
    if len(rows) < 2 or len(cols) < 2:
        return 0.0

    row_index = {name: i for i, name in enumerate(rows)}
    col_index = {name: i for i, name in enumerate(cols)}
    table = [[0] * len(cols) for _ in rows]
    for a, b in pairs:
        table[row_index[a]][col_index[b]] += 1

    n = len(pairs)
    row_totals = [sum(row) for row in table]
    col_totals = [sum(table[r][c] for r in range(len(rows))) for c in range(len(cols))]

    chi_square = 0.0
    for r in range(len(rows)):
        for c in range(len(cols)):
            expected = row_totals[r] * col_totals[c] / n
            if expected > 0:
                chi_square += (table[r][c] - expected) ** 2 / expected

    denominator = n * min(len(rows) - 1, len(cols) - 1)
    return round(math.sqrt(chi_square / denominator), 4) if denominator else 0.0


def grouping_report(pairs: list[tuple[str, str]], label: str) -> dict:
    """Describe how well a grouping key predicts the ground truth category."""
    by_group: dict[str, Counter] = defaultdict(Counter)
    global_counts: Counter = Counter()
    for group, category in pairs:
        by_group[group][category] += 1
        global_counts[category] += 1

    within = [entropy(counts) for counts in by_group.values()]
    global_entropy = entropy(global_counts)
    mean_within = sum(within) / len(within) if within else 0.0
    pure = sum(1 for value in within if value == 0.0)

    return {
        "grouping": label,
        "groups": len(by_group),
        "signals": len(pairs),
        "cramers_v": cramers_v(pairs),
        "global_category_entropy_bits": round(global_entropy, 4),
        "mean_within_group_entropy_bits": round(mean_within, 4),
        "entropy_reduction_bits": round(global_entropy - mean_within, 4),
        "pure_groups": pure,
        "pure_group_fraction": round(pure / len(by_group), 4) if by_group else 0.0,
    }


def build_correlation_report(scenarios: list[Scenario]) -> dict:
    """Compare this generator's grouping against the Level 5 assignment."""
    generated: list[tuple[str, str]] = []
    level5: list[tuple[str, str]] = []

    position = 0
    for scenario in scenarios:
        category = scenario.ground_truth.expected_conclusion
        regime = scenario.ground_truth.regime.value
        truth = f"{regime}:{category}"
        for signal in scenario.signals:
            entity = str(signal.entity) if signal.entity else "none"
            generated.append((entity, truth))
            level5.append((f"device:synthetic-device-{position % LEVEL5_ENTITY_POOL:02d}", truth))
            position += 1

    return {
        "generated_entities": grouping_report(generated, "scenario scoped entity"),
        "level5_reconstruction": grouping_report(
            level5, "index modulo 16, as Level 5 assigned"
        ),
    }


def main() -> int:
    """Generate, freeze and report on the suite."""
    parser = argparse.ArgumentParser(description="Level 7 scenario suite generator.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenarios", type=int, default=400)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    scenarios = generate_suite(total=args.scenarios, seed=args.seed)
    digest = suite_hash(scenarios)

    suite_path = RESULTS_DIR / "suite.jsonl"
    with suite_path.open("w", encoding="utf-8") as handle:
        for scenario in scenarios:
            handle.write(json.dumps(scenario.to_dict(), separators=(",", ":")) + "\n")

    per_regime = Counter(s.ground_truth.regime.value for s in scenarios)
    per_category = Counter(s.ground_truth.expected_conclusion for s in scenarios)
    diversity = Counter(len(set(s.sources)) for s in scenarios)

    situation_diversity: Counter = Counter()
    situation_diversity_by_regime: dict[str, Counter] = defaultdict(Counter)
    for scenario in scenarios:
        grouped: dict[str, set[str]] = defaultdict(set)
        for signal in scenario.signals:
            grouped[str(signal.entity)].add(signal.source)
        for sources_seen in grouped.values():
            situation_diversity[len(sources_seen)] += 1
            situation_diversity_by_regime[scenario.ground_truth.regime.value][
                len(sources_seen)
            ] += 1
    entity_counts = Counter(len(s.entities) for s in scenarios)
    signals_total = sum(len(s.signals) for s in scenarios)
    situations_total = sum(len(s.entities) for s in scenarios)
    abstained_total = sum(
        1 for s in scenarios for sig in s.signals if sig.abstained
    )

    correlation = build_correlation_report(scenarios)

    manifest = {
        "seed": args.seed,
        "generated_at_utc": started.isoformat(),
        "suite_hash": digest,
        "scenario_count": len(scenarios),
        "signal_count": signals_total,
        "situation_count_under_entity_grouping": situations_total,
        "abstained_signal_count": abstained_total,
        "abstained_signal_fraction": round(abstained_total / signals_total, 4),
        "scenarios_per_regime": dict(sorted(per_regime.items())),
        "scenarios_per_expected_conclusion": dict(sorted(per_category.items())),
        "source_diversity_per_scenario": dict(sorted(diversity.items())),
        "source_diversity_per_situation": dict(sorted(situation_diversity.items())),
        "source_diversity_per_situation_by_regime": {
            regime: dict(sorted(counts.items()))
            for regime, counts in sorted(situation_diversity_by_regime.items())
        },
        "situations_at_diversity_one": situation_diversity.get(1, 0),
        "situations_at_diversity_one_fraction": round(
            situation_diversity.get(1, 0) / situations_total, 4
        ),
        "entity_count_distribution": dict(sorted(entity_counts.items())),
        "suite_path": str(suite_path.relative_to(PROJECT_ROOT)),
        "entity_correlation": correlation,
    }
    (RESULTS_DIR / "suite_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    run_manifest = build_run_manifest(
        experiment="level7_generate_suite",
        seed=args.seed,
        config={"scenarios": args.scenarios},
        started_at=started,
        project_root=PROJECT_ROOT,
        dataset=suite_path,
        extra={"suite_hash": digest},
    )
    write_manifest(run_manifest, RESULTS_DIR / "manifest_generate.json")

    print(f"seed {args.seed}")
    print(f"suite hash {digest}")
    print(f"scenarios {len(scenarios)}  signals {signals_total}  "
          f"situations under entity grouping {situations_total}")
    print()
    print("scenarios per regime")
    for name, count in sorted(per_regime.items()):
        print(f"  {name:<16} {count}")
    print()
    print("source diversity per situation, which is the unit the reasoner sees")
    for value, count in sorted(situation_diversity.items()):
        print(f"  {value} sources     {count} situations  "
              f"{count / situations_total * 100:.1f}%")
    print(f"  situations stuck at diversity one: {situation_diversity.get(1, 0)}"
          f" of {situations_total}")
    print()
    print("source diversity per situation, by regime")
    for regime, counts in sorted(situation_diversity_by_regime.items()):
        rendered = "  ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        print(f"  {regime:<16} {rendered}")
    print()
    print("source diversity per scenario, union across its entities")
    for value, count in sorted(diversity.items()):
        print(f"  {value} sources     {count} scenarios  "
              f"{count / len(scenarios) * 100:.1f}%")
    print()
    print("entity count distribution")
    for value, count in sorted(entity_counts.items()):
        print(f"  {value} entities    {count} scenarios")
    print()
    print("entity to ground truth association")
    for key in ("generated_entities", "level5_reconstruction"):
        row = correlation[key]
        print(f"  {row['grouping']}")
        print(f"    groups                        {row['groups']}")
        print(f"    Cramers V                     {row['cramers_v']}")
        print(f"    global category entropy       {row['global_category_entropy_bits']} bits")
        print(f"    mean within group entropy     {row['mean_within_group_entropy_bits']} bits")
        print(f"    entropy reduction             {row['entropy_reduction_bits']} bits")
        print(f"    pure groups                   {row['pure_groups']} of {row['groups']} "
              f"({row['pure_group_fraction'] * 100:.1f}%)")
    print()
    print(f"written to {suite_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
