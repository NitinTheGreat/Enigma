"""
Module: scripts/level9_signal_type_probe.py

Tests whether the signal type distribution could carry narrative identity.

Task 2 of the Level 9 preparation proposes widening the context with the
distribution of Signal.signal_type within a situation, on the grounds that it
already exists, is not raw network content, and plausibly says which
narrative a situation is about. That is worth checking before any model call
is spent on it, because the widening is only informative if the field it adds
actually separates the narratives.

The test mirrors the narrative identity test in level9_context_separation.py
so the two are comparable: the same six categories, the same group aware
cross validation with a scenario never spanning folds, and the same
comparison against always predicting the most common category. The features
here are the share each signal type takes within the situation, which is what
a widened context would expose.
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

import numpy as np  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.model_selection import GroupKFold, cross_val_score  # noqa: E402

from scenarios.generator import CATEGORIES  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "level9_prep"


def category_of(scenario) -> str | None:
    """Return the narrative a scenario is about, if it has one."""
    keywords = set(scenario.ground_truth.conclusion_keywords)
    if not keywords:
        return None
    for category in CATEGORIES:
        if keywords & set(category.keywords):
            return category.name
    return None


def main() -> int:
    """Measure how much narrative identity signal type carries."""
    parser = argparse.ArgumentParser(description="Signal type probe.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)

    types = sorted({s.signal_type for sc in scenarios for s in sc.signals})

    units: list[dict[str, Any]] = []
    for scenario in scenarios:
        label = category_of(scenario)
        if label is None:
            continue
        grouped: dict[str, list] = defaultdict(list)
        for signal in scenario.signals:
            grouped[str(getattr(signal.entity, "identifier", signal.entity))].append(signal)
        for entity, signals in grouped.items():
            counts = Counter(s.signal_type for s in signals)
            total = sum(counts.values())
            units.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "entity": entity,
                    "category": label,
                    "signals": total,
                    "shares": {t: counts.get(t, 0) / total for t in types},
                    "counts": {t: counts.get(t, 0) for t in types},
                }
            )

    sources = sorted({s.source for sc in scenarios for s in sc.signals})
    for unit in units:
        scenario = next(sc for sc in scenarios if sc.scenario_id == unit["scenario_id"])
        signals = [
            s
            for s in scenario.signals
            if str(getattr(s.entity, "identifier", s.entity)) == unit["entity"]
        ]
        counts = Counter(s.source for s in signals)
        total = max(sum(counts.values()), 1)
        unit["source_shares"] = {src: counts.get(src, 0) / total for src in sources}

    y = np.array([u["category"] for u in units])
    groups = np.array([u["scenario_id"] for u in units])
    base = max(Counter(y).values()) / len(y)
    splits = min(5, len(set(groups)))

    def measure(matrix: np.ndarray) -> tuple[float, float]:
        """Return mean and deviation of group aware cross validated accuracy."""
        found = cross_val_score(
            RandomForestClassifier(
                n_estimators=300, random_state=args.seed, n_jobs=-1, min_samples_leaf=2
            ),
            matrix,
            y,
            groups=groups,
            cv=GroupKFold(n_splits=splits),
            scoring="accuracy",
        )
        return float(found.mean()), float(found.std())

    X = np.array([[u["shares"][t] for t in types] for u in units])
    accuracy, deviation = measure(X)
    lift = accuracy - base

    X_source = np.array([[u["source_shares"][src] for src in sources] for u in units])
    source_accuracy, source_deviation = measure(X_source)

    X_both = np.concatenate([X, X_source], axis=1)
    both_accuracy, both_deviation = measure(X_both)

    detectors_by_category = {
        c.name: tuple(d.value for d in c.detectors) for c in CATEGORIES
    }
    collisions: dict[str, list[str]] = defaultdict(list)
    for name, tup in detectors_by_category.items():
        collisions["+".join(tup)].append(name)
    indistinguishable = {k: v for k, v in collisions.items() if len(v) > 1}

    scores = type("S", (), {"std": lambda self=None: deviation})()

    per_category: dict[str, dict[str, float]] = {}
    for label in sorted(set(y.tolist())):
        rows = [u for u in units if u["category"] == label]
        pooled: Counter = Counter()
        for row in rows:
            pooled.update(row["counts"])
        total = sum(pooled.values())
        per_category[label] = {
            t: round(pooled.get(t, 0) / total, 4) if total else 0.0 for t in types
        }

    usable = lift >= 0.05
    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "signal_types": types,
        "situations_with_a_narrative": len(units),
        "scenarios_with_a_narrative": int(len(set(groups))),
        "categories": sorted(set(y.tolist())),
        "cross_validation": "GroupKFold by scenario, so no scenario spans folds",
        "signal_type": {
            "accuracy_mean": round(accuracy, 4),
            "accuracy_sd": round(deviation, 4),
            "lift_over_base_rate": round(lift, 4),
        },
        "source": {
            "accuracy_mean": round(source_accuracy, 4),
            "accuracy_sd": round(source_deviation, 4),
            "lift_over_base_rate": round(source_accuracy - base, 4),
        },
        "signal_type_and_source": {
            "accuracy_mean": round(both_accuracy, 4),
            "accuracy_sd": round(both_deviation, 4),
            "lift_over_base_rate": round(both_accuracy - base, 4),
        },
        "detectors_by_category": detectors_by_category,
        "categories_sharing_a_detector_signature": indistinguishable,
        "majority_class_base_rate": round(float(base), 4),
        "signal_type_share_per_category": per_category,
        "would_carry_narrative_identity": bool(usable),
        "reading": (
            "The widening proposed in Task 2 can only make the narrative "
            "regime dependent if the field it adds separates the narratives. "
            "A lift at or below zero means it does not, and that adding it "
            "would at best change nothing and at worst point the model at the "
            "wrong narrative."
        ),
    }
    (RESULTS_DIR / f"signal_type_probe_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    csv_path = RESULTS_DIR / f"signal_type_probe_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "category"] + types)
        for label, shares in per_category.items():
            writer.writerow([args.seed, label] + [shares[t] for t in types])

    print(f"seed {args.seed}   suite {suite_path.name}")
    print(f"signal types {types}")
    print(
        f"situations with a narrative {len(units)} "
        f"over {len(set(groups))} scenarios"
    )
    print()
    header = f"{'category':<24}" + "".join(f"{t[:14]:>16}" for t in types)
    print(header)
    print("-" * len(header))
    for label, shares in per_category.items():
        print(f"{label:<24}" + "".join(f"{shares[t]:>16.3f}" for t in types))
    print()
    print(f"{'feature set':<28}{'accuracy':>12}{'sd':>9}{'base':>9}{'lift':>10}")
    print("-" * 68)
    for label, acc, dev in (
        ("signal_type shares", accuracy, deviation),
        ("source shares", source_accuracy, source_deviation),
        ("both together", both_accuracy, both_deviation),
    ):
        print(f"{label:<28}{acc:>12.4f}{dev:>9.4f}{base:>9.4f}{acc - base:>+10.4f}")
    print()
    print("detector families per category")
    for name, tup in detectors_by_category.items():
        print(f"  {name:<22} {'+'.join(tup)}")
    if indistinguishable:
        print()
        print("categories sharing an identical detector signature:")
        for signature, names in indistinguishable.items():
            print(f"  {signature:<22} {names}")
    print()
    if usable:
        print("Signal type does carry narrative identity, so the Task 2")
        print("widening is worth running.")
    else:
        print("Signal type does NOT carry narrative identity. The generator")
        print("draws it from detector families rather than from the scenario's")
        print("narrative, so widening the context with it cannot make the")
        print("narrative regime dependent.")
    print()
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
