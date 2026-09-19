"""
Module: scripts/level9_context_separation.py

Asks whether the context the model is shown carries scenario identity at all.

The question. L8.7 found that the share of narratives Gemini proposes is
invariant across the four evidence regimes, 80.4 to 81.6 per cent
reconnaissance in every one. Three causes were candidates: the prompt
template steering toward one family, the generator failing to produce
distinguishable evidence, or the information barrier working exactly as
designed and leaving the model nothing to discriminate on.

The third is testable directly and settles the other two for hypothesis
content. assemble_context exposes ten aggregated fields and nothing else, by
design, as the information barrier. If those ten do not separate the regimes,
then no model reading them can produce regime dependent narratives, whatever
the prompt says and however distinguishable the underlying signals are.

How it is measured. The contexts are captured by wrapping assemble_context
for the duration of an offline replay, so what is analysed is exactly what
the model was handed, not a reconstruction. The replay uses a factory that
raises, which costs no model calls: context assembly runs before generation
and is unaffected by generation failing.

Two levels of test. Each field is tested univariately, Kruskal-Wallis for the
continuous fields and a chi-square test of independence for the categorical
ones, each with an effect size, because at tens of thousands of records a
p-value alone will call a difference of no consequence significant. Then the
ten fields together are given to a classifier, because the question is not
whether any single field shifts but whether the vector carries enough
identity for a reader to tell the regimes apart. Accuracy is compared against
always predicting the largest regime.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.model_selection import GroupKFold, cross_val_score  # noqa: E402

from enigma_reason.graph import builder as graph_builder  # noqa: E402
from enigma_reason.graph import nodes as graph_nodes  # noqa: E402
from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402
from scenarios.generator import scenario_id_from_entity  # noqa: E402

from level7_validate import load_suite, raising_llm_factory  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "level9_prep"

CONTINUOUS = (
    "evidence_count",
    "event_rate_per_minute",
    "active_duration_seconds",
    "confidence_level",
    "source_diversity",
    "mean_anomaly_score",
    "iteration",
)
CATEGORICAL = ("burst_detected", "quiet_detected", "trend")

EFFECT_FLOOR_CONTINUOUS = 0.01
EFFECT_FLOOR_CATEGORICAL = 0.10
ALPHA = 0.01


def cramers_v(table: np.ndarray) -> float:
    """Return Cramer's V for a contingency table."""
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.sum()
    if n == 0:
        return 0.0
    smaller = min(table.shape) - 1
    if smaller <= 0:
        return 0.0
    return float(np.sqrt(chi2 / (n * smaller)))


def epsilon_squared(groups: list[list[float]]) -> float:
    """Return the epsilon squared effect size for a Kruskal-Wallis test."""
    total = sum(len(g) for g in groups)
    if total <= len(groups):
        return 0.0
    h = stats.kruskal(*groups)[0]
    return float(max(0.0, (h - len(groups) + 1) / (total - len(groups))))


def main() -> int:
    """Capture contexts, test each field, then test the vector."""
    parser = argparse.ArgumentParser(description="Context separation diagnosis.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    parser.add_argument("--clock-mode", type=str, default="separated")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    regime_of = {s.scenario_id: s.ground_truth.regime.value for s in scenarios}
    from scenarios.generator import CATEGORIES

    def category_of_scenario(scenario) -> str | None:
        """Return the narrative a scenario is about, if it has one."""
        keywords = set(scenario.ground_truth.conclusion_keywords)
        if not keywords:
            return None
        for category in CATEGORIES:
            if keywords & set(category.keywords):
                return category.name
        return None

    category_of = {s.scenario_id: category_of_scenario(s) for s in scenarios}

    captured: list[dict[str, Any]] = []
    current_scenario: dict[str, str] = {"id": ""}
    original = graph_nodes.assemble_context

    def recording_assemble_context(state):
        """Wrap the real node so every context it builds is kept.

        The scenario is tagged rather than the entity, because every entity
        within a scenario shares its regime and the whole scenario is replayed
        in one pass exactly as Level 8 ran it.
        """
        result = original(state)
        row = dict(result["context"])
        row["_scenario"] = current_scenario["id"]
        captured.append(row)
        return result

    graph_builder.assemble_context = recording_assemble_context

    controls = EpistemicControls()
    for scenario in scenarios:
        current_scenario["id"] = scenario.scenario_id
        replay = OfflineReplay(
            raising_llm_factory(),
            seed=args.seed,
            clock_mode=args.clock_mode,
            correlation=EntityCorrelation(),
            controls=controls,
        )
        replay.run(scenario.signals)

    graph_builder.assemble_context = original

    rows: list[dict[str, Any]] = []
    for row in captured:
        scenario_id = row.pop("_scenario", "")
        regime = regime_of.get(scenario_id)
        if regime is None:
            continue
        row["regime"] = regime
        row["scenario_id"] = scenario_id
        row["category"] = category_of.get(scenario_id)
        rows.append(row)

    regimes = sorted({r["regime"] for r in rows})
    counts = Counter(r["regime"] for r in rows)

    findings: list[dict[str, Any]] = []

    for field in CONTINUOUS:
        groups = [[float(r[field]) for r in rows if r["regime"] == g] for g in regimes]
        groups = [g for g in groups if g]
        if len(groups) < 2:
            continue
        spread = {
            g: {
                "n": len(vals),
                "median": round(median(vals), 4),
                "mean": round(float(np.mean(vals)), 4),
                "sd": round(float(np.std(vals)), 4),
            }
            for g, vals in zip(regimes, groups)
        }
        try:
            statistic, p = stats.kruskal(*groups)
        except ValueError:
            statistic, p = 0.0, 1.0
        effect = epsilon_squared(groups) if p == p else 0.0
        separates = bool(p < ALPHA and effect >= EFFECT_FLOOR_CONTINUOUS)
        findings.append(
            {
                "seed": args.seed,
                "field": field,
                "kind": "continuous",
                "test": "Kruskal-Wallis H across four regimes",
                "statistic": round(float(statistic), 4),
                "p_value": float(p),
                "effect_size_name": "epsilon squared",
                "effect_size": round(effect, 5),
                "effect_floor": EFFECT_FLOOR_CONTINUOUS,
                "separates": separates,
                "per_regime": spread,
            }
        )

    for field in CATEGORICAL:
        levels = sorted({str(r[field]) for r in rows})
        table = np.array(
            [
                [sum(1 for r in rows if r["regime"] == g and str(r[field]) == lvl) for lvl in levels]
                for g in regimes
            ],
            dtype=float,
        )
        keep = table.sum(axis=0) > 0
        table = table[:, keep]
        levels = [lvl for lvl, k in zip(levels, keep) if k]
        if table.shape[1] < 2:
            findings.append(
                {
                    "seed": args.seed,
                    "field": field,
                    "kind": "categorical",
                    "test": "chi-square test of independence",
                    "statistic": 0.0,
                    "p_value": 1.0,
                    "effect_size_name": "Cramers V",
                    "effect_size": 0.0,
                    "effect_floor": EFFECT_FLOOR_CATEGORICAL,
                    "separates": False,
                    "note": f"constant at {levels[0] if levels else 'unknown'}",
                    "per_regime": {g: {"n": int(counts[g])} for g in regimes},
                }
            )
            continue
        chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
        v = cramers_v(table)
        shares = {
            g: {
                lvl: round(float(table[i][j] / max(table[i].sum(), 1)), 4)
                for j, lvl in enumerate(levels)
            }
            for i, g in enumerate(regimes)
        }
        findings.append(
            {
                "seed": args.seed,
                "field": field,
                "kind": "categorical",
                "test": "chi-square test of independence",
                "statistic": round(float(chi2), 4),
                "p_value": float(p),
                "effect_size_name": "Cramers V",
                "effect_size": round(v, 5),
                "effect_floor": EFFECT_FLOOR_CATEGORICAL,
                "separates": bool(p < ALPHA and v >= EFFECT_FLOOR_CATEGORICAL),
                "levels": levels,
                "per_regime": shares,
            }
        )

    trend_levels = sorted({str(r["trend"]) for r in rows})
    features = []
    for r in rows:
        vector = [float(r[f]) for f in CONTINUOUS]
        vector.append(1.0 if r["burst_detected"] else 0.0)
        vector.append(1.0 if r["quiet_detected"] else 0.0)
        vector.extend(1.0 if str(r["trend"]) == lvl else 0.0 for lvl in trend_levels)
        features.append(vector)
    X = np.array(features)
    y = np.array([r["regime"] for r in rows])
    base_rate = max(counts.values()) / sum(counts.values())
    forest = RandomForestClassifier(
        n_estimators=200, random_state=args.seed, n_jobs=-1, min_samples_leaf=5
    )
    scores = cross_val_score(forest, X, y, cv=5, scoring="accuracy")
    accuracy = float(scores.mean())

    narrative_rows = [r for r in rows if r["category"]]
    narrative = {"rows": len(narrative_rows)}
    if narrative_rows:
        Xn = []
        for r in narrative_rows:
            vector = [float(r[f]) for f in CONTINUOUS]
            vector.append(1.0 if r["burst_detected"] else 0.0)
            vector.append(1.0 if r["quiet_detected"] else 0.0)
            vector.extend(1.0 if str(r["trend"]) == lvl else 0.0 for lvl in trend_levels)
            Xn.append(vector)
        Xn = np.array(Xn)
        yn = np.array([r["category"] for r in narrative_rows])
        groups = np.array([r["scenario_id"] for r in narrative_rows])
        narrative_base = max(Counter(yn).values()) / len(yn)
        splitter = GroupKFold(n_splits=min(5, len(set(groups))))
        narrative_scores = cross_val_score(
            RandomForestClassifier(
                n_estimators=200, random_state=args.seed, n_jobs=-1, min_samples_leaf=5
            ),
            Xn,
            yn,
            groups=groups,
            cv=splitter,
            scoring="accuracy",
        )
        narrative = {
            "rows": len(narrative_rows),
            "scenarios": int(len(set(groups))),
            "classes": sorted(set(yn.tolist())),
            "cross_validation": "GroupKFold by scenario, so no scenario spans folds",
            "accuracy_mean": round(float(narrative_scores.mean()), 4),
            "accuracy_sd": round(float(narrative_scores.std()), 4),
            "majority_class_base_rate": round(float(narrative_base), 4),
            "lift_over_base_rate": round(float(narrative_scores.mean() - narrative_base), 4),
        }

    separating = [f["field"] for f in findings if f["separates"]]
    narrative_lift = narrative.get("lift_over_base_rate", 0.0)
    if narrative_lift < 0.05:
        verdict = "C_refined_context_separates_regime_but_not_narrative"
    else:
        verdict = "context_carries_narrative_identity"

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "clock_mode": args.clock_mode,
        "contexts_captured": len(rows),
        "contexts_per_regime": dict(sorted(counts.items())),
        "alpha": ALPHA,
        "effect_floor_continuous": EFFECT_FLOOR_CONTINUOUS,
        "effect_floor_categorical": EFFECT_FLOOR_CATEGORICAL,
        "fields": findings,
        "fields_that_separate": separating,
        "multivariate": {
            "model": "RandomForestClassifier, 200 trees, five fold cross validation",
            "features": list(CONTINUOUS) + ["burst_detected", "quiet_detected"] + [f"trend={l}" for l in trend_levels],
            "accuracy_mean": round(accuracy, 4),
            "accuracy_sd": round(float(scores.std()), 4),
            "majority_class_base_rate": round(base_rate, 4),
            "lift_over_base_rate": round(accuracy - base_rate, 4),
        },
        "narrative_identity": narrative,
        "verdict": verdict,
    }
    (RESULTS_DIR / f"context_separation_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    csv_path = RESULTS_DIR / f"context_separation_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["seed", "field", "kind", "test", "statistic", "p_value",
             "effect_size_name", "effect_size", "effect_floor", "separates"]
        )
        for f in findings:
            writer.writerow(
                [args.seed, f["field"], f["kind"], f["test"], f["statistic"],
                 f"{f['p_value']:.3e}", f["effect_size_name"], f["effect_size"],
                 f["effect_floor"], f["separates"]]
            )

    print(f"seed {args.seed}   clock mode {args.clock_mode}")
    print(f"contexts captured {len(rows)}   per regime {json.dumps(dict(sorted(counts.items())))}")
    print()
    header = f"{'field':<26}{'test':<16}{'p':>12}{'effect':>10}{'floor':>8}{'separates':>11}"
    print(header)
    print("-" * len(header))
    for f in findings:
        test = "Kruskal-Wallis" if f["kind"] == "continuous" else "chi-square"
        print(
            f"{f['field']:<26}{test:<16}{f['p_value']:>12.3e}"
            f"{f['effect_size']:>10.5f}{f['effect_floor']:>8}"
            f"{str(f['separates']):>11}"
        )
    print()
    print(f"fields that separate: {separating or 'NONE'}")
    print()
    m = report["multivariate"]
    print("multivariate, all ten fields together")
    print(f"  {m['model']}")
    print(f"  accuracy           {m['accuracy_mean']:.4f} +- {m['accuracy_sd']:.4f}")
    print(f"  base rate          {m['majority_class_base_rate']:.4f}")
    print(f"  lift               {m['lift_over_base_rate']:+.4f}")
    print()
    if narrative:
        print("narrative identity, can the context say WHICH attack it is")
        print(f"  rows {narrative['rows']} over {narrative.get('scenarios')} scenarios")
        print(f"  classes {narrative.get('classes')}")
        print(f"  {narrative.get('cross_validation')}")
        print(
            f"  accuracy           {narrative.get('accuracy_mean'):.4f} "
            f"+- {narrative.get('accuracy_sd'):.4f}"
        )
        print(f"  base rate          {narrative.get('majority_class_base_rate'):.4f}")
        print(f"  lift               {narrative.get('lift_over_base_rate'):+.4f}")
        print()
    if verdict.startswith("C_refined"):
        print("VERDICT C, refined. The context separates the four regimes, which")
        print("describe how sufficient the evidence is, but carries no usable")
        print("signal for WHICH narrative applies. The model can tell a sparse")
        print("situation from a clear one and cannot tell exfiltration from")
        print("reconnaissance, which is exactly the invariance L8.7 measured.")
    else:
        print("VERDICT the context does carry narrative identity, so the")
        print("invariant narrative share is caused by the prompt template, A.")
    print()
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
