"""
Module: scripts/level9_analyse.py

Scores every Level 9 cell and computes the factorial analysis.

Metric tiers are as declared in L8.1.4, before the run. The four live metrics
depend only on whether the system concluded or abstained and on the evidence
count at termination, so none of them consults a keyword or depends on
narrative identity. The two conclusion metrics are carried but labelled, and
the clear regime is reported separately from the three abstain truth regimes
because it is the only one where narrative matching is consulted.

Main effects are computed the way a factorial asks for them: for each switch,
the mean of the cells where it is ablated minus the mean of the cells where
it is not, averaged over every combination of the other three. Doing it per
seed first and then taking the deviation across seeds gives an honest spread,
because the five seeds are the only replication this design has.

Two way interactions are computed as half the difference between the effect
of one switch when a second is ablated and its effect when that second is
not. They are reported, and they are reported as underpowered, because five
seeds is enough to see a main effect that moves a metric by tenths and is not
enough to resolve an interaction term of the size these turn out to be.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from itertools import combinations, product
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scenarios.generator import Regime  # noqa: E402
from scenarios.scoring import score_run  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "ablation"

SWITCHES = ("U", "S", "A", "P")
LIVE_METRICS = (
    "abstention_rate",
    "appropriate_abstention_rate",
    "inappropriate_abstention_rate",
    "premature_convergence_rate",
)
CARRIED_METRICS = ("correct_conclusion_rate", "false_conclusion_rate")
DEAD_METRICS = ("single_iteration_conclusion_rate", "mean_iterations_to_termination")
ALL_METRICS = LIVE_METRICS + CARRIED_METRICS + DEAD_METRICS


def configuration_name(ablated: str) -> str:
    """Return the stable cell name for a set of disabled switches."""
    return ablated if ablated else "allon"


def threshold_tag(threshold: float) -> str:
    """Return the filename fragment for a threshold."""
    return f"t{int(round(threshold * 100)):03d}"


def convergence_statistics(path: Path, threshold: float) -> dict[str, Any]:
    """Summarise convergence and termination for one cell."""
    scores: list[float] = []
    reasons: dict[str, int] = defaultdict(int)
    terminal = 0
    converged = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        score = float(record.get("convergence_score") or 0.0)
        scores.append(score)
        if record.get("terminated"):
            terminal += 1
            reasons[str(record.get("termination_reason"))] += 1
            if score >= threshold:
                converged += 1
    return {
        "iteration_records": len(scores),
        "max_convergence": round(max(scores), 4) if scores else 0.0,
        "mean_convergence": round(mean(scores), 4) if scores else 0.0,
        "analyses_terminated": terminal,
        "convergence_fraction": round(converged / terminal, 4) if terminal else 0.0,
        "termination_reasons": dict(reasons),
    }


def main() -> int:
    """Score every cell and write the factorial analysis."""
    parser = argparse.ArgumentParser(description="Level 9 analysis.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--thresholds", type=str, default="0.30,0.50,0.80")
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
    ablations = [
        "".join(c) for n in range(len(SWITCHES) + 1) for c in combinations(SWITCHES, n)
    ]

    cells: list[dict[str, Any]] = []
    missing: list[str] = []
    for ablated, threshold, seed in product(ablations, thresholds, seeds):
        name = f"{configuration_name(ablated)}_{threshold_tag(threshold)}_{seed}"
        path = RESULTS_DIR / f"{name}.jsonl"
        entity_path = RESULTS_DIR / f"{name}_entities.json"
        description_path = RESULTS_DIR / f"{name}_descriptions.json"
        if not (path.exists() and entity_path.exists()):
            missing.append(name)
            continue
        entities = json.loads(entity_path.read_text(encoding="utf-8"))
        descriptions = (
            json.loads(description_path.read_text(encoding="utf-8"))
            if description_path.exists()
            else {}
        )
        outcomes, overall, per_regime = score_run(
            path, scenarios, entities, descriptions
        )
        row: dict[str, Any] = {
            "seed": seed,
            "configuration": configuration_name(ablated),
            "ablated": ablated or "none",
            "convergence_threshold": threshold,
            "situations_scored": overall.situations,
        }
        for switch in SWITCHES:
            row[f"{switch}_enabled"] = switch not in ablated
        for metric in ALL_METRICS:
            row[metric] = getattr(overall, metric)
        row.update(convergence_statistics(path, threshold))
        row["per_regime"] = {k: v.to_dict() for k, v in per_regime.items()}
        cells.append(row)

    if not cells:
        print("no scored cells found, has the run finished writing entity maps?")
        return 1

    flat_fields = [k for k in cells[0] if k not in ("per_regime", "termination_reasons")]
    cells_csv = RESULTS_DIR / f"cells_seed{args.seed}.csv"
    with cells_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=flat_fields + ["termination_reasons"])
        writer.writeheader()
        for row in cells:
            flat = {k: row[k] for k in flat_fields}
            flat["termination_reasons"] = json.dumps(row["termination_reasons"])
            writer.writerow(flat)

    def main_effect(metric: str, switch: str, threshold: float, regime: str | None = None):
        """Return the per seed main effect of one switch, ablated minus enabled."""
        per_seed: list[float] = []
        for seed in seeds:
            ablated_values = []
            enabled_values = []
            for row in cells:
                if row["seed"] != seed or row["convergence_threshold"] != threshold:
                    continue
                value = (
                    row["per_regime"][regime][metric]
                    if regime
                    else row[metric]
                )
                if row[f"{switch}_enabled"]:
                    enabled_values.append(value)
                else:
                    ablated_values.append(value)
            if ablated_values and enabled_values:
                per_seed.append(mean(ablated_values) - mean(enabled_values))
        return per_seed

    effects: list[dict[str, Any]] = []
    for threshold, metric, switch in product(thresholds, ALL_METRICS, SWITCHES):
        per_seed = main_effect(metric, switch, threshold)
        if not per_seed:
            continue
        effects.append(
            {
                "seed": args.seed,
                "convergence_threshold": threshold,
                "metric": metric,
                "switch": switch,
                "tier": "live"
                if metric in LIVE_METRICS
                else ("carried" if metric in CARRIED_METRICS else "dead"),
                "effect_mean": round(mean(per_seed), 4),
                "effect_sd": round(pstdev(per_seed), 4) if len(per_seed) > 1 else 0.0,
                "seeds": len(per_seed),
            }
        )

    effects_csv = RESULTS_DIR / f"main_effects_seed{args.seed}.csv"
    with effects_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(effects[0].keys()))
        writer.writeheader()
        writer.writerows(effects)

    regime_effects: list[dict[str, Any]] = []
    for threshold, metric, switch, regime in product(
        thresholds, LIVE_METRICS, SWITCHES, [r.value for r in Regime]
    ):
        per_seed = main_effect(metric, switch, threshold, regime)
        if not per_seed:
            continue
        regime_effects.append(
            {
                "seed": args.seed,
                "convergence_threshold": threshold,
                "regime": regime,
                "metric": metric,
                "switch": switch,
                "effect_mean": round(mean(per_seed), 4),
                "effect_sd": round(pstdev(per_seed), 4) if len(per_seed) > 1 else 0.0,
            }
        )

    regime_csv = RESULTS_DIR / f"regime_effects_seed{args.seed}.csv"
    with regime_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(regime_effects[0].keys()))
        writer.writeheader()
        writer.writerows(regime_effects)

    interactions: list[dict[str, Any]] = []
    for threshold, metric in product(thresholds, LIVE_METRICS):
        for first, second in combinations(SWITCHES, 2):
            per_seed: list[float] = []
            for seed in seeds:
                buckets: dict[tuple[bool, bool], list[float]] = defaultdict(list)
                for row in cells:
                    if row["seed"] != seed or row["convergence_threshold"] != threshold:
                        continue
                    key = (
                        not row[f"{first}_enabled"],
                        not row[f"{second}_enabled"],
                    )
                    buckets[key].append(row[metric])
                if len(buckets) == 4:
                    effect_when_second_ablated = mean(buckets[(True, True)]) - mean(
                        buckets[(False, True)]
                    )
                    effect_when_second_present = mean(buckets[(True, False)]) - mean(
                        buckets[(False, False)]
                    )
                    per_seed.append(
                        (effect_when_second_ablated - effect_when_second_present) / 2.0
                    )
            if per_seed:
                interactions.append(
                    {
                        "seed": args.seed,
                        "convergence_threshold": threshold,
                        "metric": metric,
                        "pair": f"{first}x{second}",
                        "interaction_mean": round(mean(per_seed), 4),
                        "interaction_sd": round(pstdev(per_seed), 4)
                        if len(per_seed) > 1
                        else 0.0,
                    }
                )

    interactions_csv = RESULTS_DIR / f"interactions_seed{args.seed}.csv"
    with interactions_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(interactions[0].keys()))
        writer.writeheader()
        writer.writerows(interactions)

    sweep: list[dict[str, Any]] = []
    for threshold in thresholds:
        rows = [c for c in cells if c["convergence_threshold"] == threshold]
        entry: dict[str, Any] = {"seed": args.seed, "convergence_threshold": threshold}
        for field in ("convergence_fraction", "max_convergence") + DEAD_METRICS:
            values = [float(r[field]) for r in rows]
            entry[f"{field}_mean"] = round(mean(values), 4)
            entry[f"{field}_sd"] = round(pstdev(values), 4) if len(values) > 1 else 0.0
        with_p = [r for r in rows if r["P_enabled"]]
        without_p = [r for r in rows if not r["P_enabled"]]
        entry["convergence_fraction_P_enabled"] = round(
            mean(float(r["convergence_fraction"]) for r in with_p), 4
        ) if with_p else 0.0
        entry["convergence_fraction_P_ablated"] = round(
            mean(float(r["convergence_fraction"]) for r in without_p), 4
        ) if without_p else 0.0
        entry["max_convergence_P_enabled"] = round(
            max(float(r["max_convergence"]) for r in with_p), 4
        ) if with_p else 0.0
        entry["max_convergence_P_ablated"] = round(
            max(float(r["max_convergence"]) for r in without_p), 4
        ) if without_p else 0.0
        sweep.append(entry)

    sweep_csv = RESULTS_DIR / f"threshold_sweep_seed{args.seed}.csv"
    with sweep_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sweep[0].keys()))
        writer.writeheader()
        writer.writerows(sweep)

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "cells_scored": len(cells),
        "cells_missing": missing,
        "seeds": seeds,
        "thresholds": thresholds,
        "metric_tiers": {
            "live": list(LIVE_METRICS),
            "carried_with_caveat": list(CARRIED_METRICS),
            "dead_at_08": list(DEAD_METRICS),
        },
        "main_effects": effects,
        "regime_effects": regime_effects,
        "interactions": interactions,
        "threshold_sweep": sweep,
        "power_statement": (
            "Five seeds. Main effects that move a metric by more than about "
            "0.05 are resolved; interaction terms are reported but are not, "
            "because the interaction estimator differences two differences "
            "and its deviation across five seeds is of the same order as the "
            "terms themselves."
        ),
    }
    (RESULTS_DIR / f"analysis_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(f"seed {args.seed}   cells scored {len(cells)}   missing {len(missing)}")
    if missing:
        print(f"  first missing: {missing[:4]}")
    print()
    for threshold in thresholds:
        print(f"=== threshold {threshold} main effects, ablated minus enabled ===")
        header = f"{'metric':<34}" + "".join(f"{s:>16}" for s in SWITCHES)
        print(header)
        print("-" * len(header))
        for metric in LIVE_METRICS:
            row = f"{metric:<34}"
            for switch in SWITCHES:
                found = [
                    e
                    for e in effects
                    if e["metric"] == metric
                    and e["switch"] == switch
                    and e["convergence_threshold"] == threshold
                ]
                row += (
                    f"{found[0]['effect_mean']:>+9.4f}+-{found[0]['effect_sd']:<5.3f}"
                    if found
                    else f"{'na':>16}"
                )
            print(row)
        print()
    print(f"written {cells_csv.relative_to(PROJECT_ROOT)}")
    print(f"written {effects_csv.relative_to(PROJECT_ROOT)}")
    print(f"written {regime_csv.relative_to(PROJECT_ROOT)}")
    print(f"written {interactions_csv.relative_to(PROJECT_ROOT)}")
    print(f"written {sweep_csv.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
