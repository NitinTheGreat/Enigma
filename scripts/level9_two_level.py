"""
Module: scripts/level9_two_level.py

The two level abstention experiment: sensor reject crossed with epistemic
control.

The claim under test is that the sensor's reject option and the reasoning
layer's epistemic controls are complementary, each catching cases the other
does not. Four cells: sensor reject on or off, epistemic control on or off.

Sensor reject off is implemented by clearing the abstained flag on every
signal before it is ingested, which is what ignoring the sensor's refusal
means. Epistemic control off is the USAP cell, all four mechanisms disabled.

Reported on the unknown attack regime specifically, which carries the highest
abstained fraction in the sub-suite at 0.5467 against 0.2285 overall, and is
where the two levels are supposed to be complementary: the sensor declines
because the traffic does not resemble its training classes, and the reasoner
declines because the evidence does not resemble any narrative it holds.

This experiment is cheap because clearing the abstained flag does not change
any prompt. Whether that is true is precisely what it measures.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from itertools import product
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / "Enigma-AIAgent" / ".env")

sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from enigma_reason.config import settings  # noqa: E402
from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.graph.runner import _default_llm_factory  # noqa: E402
from enigma_reason.observability.llm_cache import CachingLLMFactory, ResponseCache  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter, text_hash  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay, mock_llm_factory  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402
from scenarios.scoring import score_run  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
RESULTS_DIR = PROJECT_ROOT / "results" / "two_level"

METRICS = (
    "abstention_rate",
    "appropriate_abstention_rate",
    "inappropriate_abstention_rate",
    "premature_convergence_rate",
    "correct_conclusion_rate",
    "false_conclusion_rate",
)


def strip_abstention(signals):
    """Return copies of the signals with the sensor's refusal cleared."""
    cleared = []
    for signal in signals:
        cleared.append(signal.model_copy(update={"abstained": False}))
    return cleared


def main() -> int:
    """Run the four cells and report whether the levels are complementary."""
    parser = argparse.ArgumentParser(description="Two level abstention.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--llm", choices=("real", "mock"), default="real")
    parser.add_argument("--regime", type=str, default="unknown_attack")
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    abstained_total = sum(1 for s in scenarios for x in s.signals if x.abstained)
    signals_total = sum(len(s.signals) for s in scenarios)

    caches: dict[int, ResponseCache] = {}
    factories: dict[int, Any] = {}
    for seed in seeds:
        if args.llm == "mock":
            factories[seed] = mock_llm_factory(seed=seed)
            continue
        cache_path = RESULTS_DIR / f"cache_seed{seed}.json"
        warm = ABLATION_DIR / f"cache_seed{seed}.json"
        if not cache_path.exists() and warm.exists():
            import shutil

            shutil.copy2(warm, cache_path)
        cache = ResponseCache(cache_path, model=settings.gemini_model)
        caches[seed] = cache
        factories[seed] = CachingLLMFactory(_default_llm_factory, cache)

    cells: list[dict[str, Any]] = []
    for sensor_reject, epistemic, seed in product((True, False), (True, False), seeds):
        ablated = "" if epistemic else "USAP"
        name = (
            f"sensor{'On' if sensor_reject else 'Off'}"
            f"_epistemic{'On' if epistemic else 'Off'}_{seed}"
        )
        path = RESULTS_DIR / f"{name}.jsonl"
        if path.exists():
            path.unlink()

        descriptions: dict[str, str] = {}
        entities: dict[str, str] = {}

        def harvest(situation, final_state) -> None:
            """Record hypothesis text and the entity a situation belongs to."""
            for hypothesis in final_state.get("hypotheses", []):
                description = str(hypothesis.get("description", ""))
                descriptions[text_hash(description)] = description
            evidence = situation.evidence
            if evidence and evidence[0].entity:
                entities[str(situation.situation_id)] = str(evidence[0].entity)

        controls = EpistemicControls(
            unknown_hypothesis_enabled="U" not in ablated,
            sanity_gate_enabled="S" not in ablated,
            asymmetric_decay_enabled="A" not in ablated,
            persistence_required="P" not in ablated,
        )

        with RunLogWriter(path) as writer:
            for scenario in scenarios:
                signals = scenario.signals if sensor_reject else strip_abstention(
                    scenario.signals
                )
                replay = OfflineReplay(
                    factories[seed],
                    run_log=writer,
                    seed=seed,
                    correlation=EntityCorrelation(),
                    on_analysis=harvest,
                    controls=controls,
                )
                replay.run(signals)
            writer.flush()

        _, overall, per_regime = score_run(path, scenarios, entities, descriptions)
        focus = per_regime[args.regime].to_dict()
        row: dict[str, Any] = {
            "seed": seed,
            "sensor_reject": sensor_reject,
            "epistemic_control": epistemic,
            "cell": f"sensor={'on' if sensor_reject else 'off'}, "
            f"epistemic={'on' if epistemic else 'off'}",
            "situations_overall": overall.situations,
            "situations_regime": focus["situations"],
        }
        for metric in METRICS:
            row[f"overall_{metric}"] = getattr(overall, metric)
            row[f"{args.regime}_{metric}"] = focus[metric]
        cells.append(row)
        print(
            f"  {row['cell']:<38} seed {seed:<5} "
            f"{args.regime} abstention {row[f'{args.regime}_abstention_rate']:.4f}",
            flush=True,
        )

    for cache in caches.values():
        cache.save()

    csv_path = RESULTS_DIR / f"cells_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer_csv = csv.DictWriter(handle, fieldnames=list(cells[0].keys()))
        writer_csv.writeheader()
        writer_csv.writerows(cells)

    table: list[dict[str, Any]] = []
    for sensor_reject, epistemic in product((True, False), (True, False)):
        rows = [
            c
            for c in cells
            if c["sensor_reject"] == sensor_reject and c["epistemic_control"] == epistemic
        ]
        entry: dict[str, Any] = {
            "seed": args.seed,
            "sensor_reject": sensor_reject,
            "epistemic_control": epistemic,
        }
        for metric in METRICS:
            values = [float(r[f"{args.regime}_{metric}"]) for r in rows]
            entry[f"{metric}_mean"] = round(mean(values), 4)
            entry[f"{metric}_sd"] = round(pstdev(values), 4) if len(values) > 1 else 0.0
        table.append(entry)

    def cell(sensor: bool, epistemic: bool, metric: str) -> float:
        """Return one cell's mean for a metric."""
        for entry in table:
            if entry["sensor_reject"] == sensor and entry["epistemic_control"] == epistemic:
                return float(entry[f"{metric}_mean"])
        return 0.0

    sensor_effect_with = cell(True, True, "abstention_rate") - cell(
        False, True, "abstention_rate"
    )
    sensor_effect_without = cell(True, False, "abstention_rate") - cell(
        False, False, "abstention_rate"
    )
    epistemic_effect = cell(True, True, "abstention_rate") - cell(
        True, False, "abstention_rate"
    )

    if abs(sensor_effect_with) < 1e-9 and abs(sensor_effect_without) < 1e-9:
        verdict = "sensor_reject_is_inert"
    elif abs(sensor_effect_with) < 0.01 and abs(epistemic_effect) > 0.05:
        verdict = "redundant_epistemic_dominates"
    else:
        verdict = "complementary_or_interacting"

    report = {
        "seed": args.seed,
        "seeds": seeds,
        "regime": args.regime,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "abstained_signal_fraction_overall": round(abstained_total / signals_total, 4),
        "llm": args.llm,
        "cells": cells,
        "four_cell_table": table,
        "sensor_effect_with_epistemic_on": round(sensor_effect_with, 6),
        "sensor_effect_with_epistemic_off": round(sensor_effect_without, 6),
        "epistemic_effect_with_sensor_on": round(epistemic_effect, 6),
        "verdict": verdict,
        "reading": (
            "Sensor reject off clears the abstained flag on every signal. If "
            "that changes nothing, the flag reaches no decision in the "
            "reasoning layer and the two levels cannot be complementary "
            "because the second never receives the first."
        ),
    }
    (RESULTS_DIR / f"two_level_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print()
    print(f"abstained signal fraction, whole sub-suite {report['abstained_signal_fraction_overall']}")
    print(f"regime under test: {args.regime}")
    print()
    header = f"{'sensor':<9}{'epistemic':<11}" + "".join(f"{m[:18]:>20}" for m in METRICS[:4])
    print(header)
    print("-" * len(header))
    for entry in table:
        print(
            f"{'on' if entry['sensor_reject'] else 'off':<9}"
            f"{'on' if entry['epistemic_control'] else 'off':<11}"
            + "".join(
                f"{entry[f'{m}_mean']:>13.4f}+-{entry[f'{m}_sd']:<5.3f}"
                for m in METRICS[:4]
            )
        )
    print()
    print(f"sensor effect on abstention, epistemic on  {sensor_effect_with:+.6f}")
    print(f"sensor effect on abstention, epistemic off {sensor_effect_without:+.6f}")
    print(f"epistemic effect on abstention, sensor on  {epistemic_effect:+.6f}")
    print()
    print(f"VERDICT {verdict}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
