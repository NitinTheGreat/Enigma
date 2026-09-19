"""
Module: scripts/level9_convergence_isolation.py

Isolates what prevents convergence: the persistence requirement, belief
inertia, or the threshold.

The sweep in the main grid showed the convergence fraction is 0.0000 at every
threshold whenever persistence is enabled, and that the highest convergence
score reached is exactly the threshold minus 0.01. That is the signature of
the clamp at nodes.py, which caps the score just below the threshold whenever
the dominant hypothesis has not persisted. This experiment separates that
from belief inertia, the other mechanism that could hold confidences down, by
crossing the two at the lowest threshold where convergence is otherwise
reachable.

Four cells at threshold 0.30, every other mechanism left on: persistence on
or off, crossed with the inertia cap at its standing 0.15 or raised high
enough never to bind. If convergence appears only when persistence is off,
persistence is the cause and inertia is not.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
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
from enigma_reason.observability.run_log import RunLogWriter  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay, mock_llm_factory  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
RESULTS_DIR = PROJECT_ROOT / "results" / "convergence_isolation"

INERTIA_OFF = 1e9


def summarise(path: Path, threshold: float) -> dict[str, Any]:
    """Return convergence and iteration statistics for one cell."""
    scores: list[float] = []
    terminal = 0
    converged = 0
    single = 0
    iterations: list[int] = []
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
            iteration = int(record.get("iteration") or 0)
            iterations.append(iteration)
            if score >= threshold:
                converged += 1
                if iteration <= 1:
                    single += 1
    return {
        "analyses": terminal,
        "convergence_fraction": round(converged / terminal, 4) if terminal else 0.0,
        "single_iteration_conclusion_rate": round(single / terminal, 4) if terminal else 0.0,
        "mean_iterations_to_termination": round(mean(iterations), 4) if iterations else 0.0,
        "max_convergence": round(max(scores), 4) if scores else 0.0,
    }


def main() -> int:
    """Cross persistence with inertia at the lowest threshold."""
    parser = argparse.ArgumentParser(description="Convergence isolation.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument("--llm", choices=("real", "mock"), default="real")
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

    factories: dict[int, Any] = {}
    caches: dict[int, ResponseCache] = {}
    for seed in seeds:
        if args.llm == "mock":
            factories[seed] = mock_llm_factory(seed=seed)
            continue
        cache_path = RESULTS_DIR / f"cache_seed{seed}.json"
        warm = ABLATION_DIR / f"cache_seed{seed}.json"
        if not cache_path.exists() and warm.exists():
            shutil.copy2(warm, cache_path)
        cache = ResponseCache(cache_path, model=settings.gemini_model)
        caches[seed] = cache
        factories[seed] = CachingLLMFactory(_default_llm_factory, cache)

    rows: list[dict[str, Any]] = []
    for persistence, inertia, seed in product((True, False), (True, False), seeds):
        name = (
            f"P{'on' if persistence else 'off'}"
            f"_inertia{'on' if inertia else 'off'}_{seed}"
        )
        path = RESULTS_DIR / f"{name}.jsonl"
        if path.exists():
            path.unlink()
        controls = EpistemicControls(
            persistence_required=persistence,
            max_confidence_delta=0.15 if inertia else INERTIA_OFF,
        )
        with RunLogWriter(path) as writer:
            for scenario in scenarios:
                replay = OfflineReplay(
                    factories[seed],
                    run_log=writer,
                    seed=seed,
                    correlation=EntityCorrelation(),
                    controls=controls,
                    convergence_threshold=args.threshold,
                )
                replay.run(scenario.signals)
            writer.flush()
        stats = summarise(path, args.threshold)
        rows.append(
            {
                "seed": seed,
                "convergence_threshold": args.threshold,
                "persistence_required": persistence,
                "inertia_enabled": inertia,
                "max_confidence_delta": 0.15 if inertia else INERTIA_OFF,
                **stats,
            }
        )
        print(
            f"  P {'on ' if persistence else 'off'}  inertia "
            f"{'on ' if inertia else 'off'}  seed {seed:<5} "
            f"convergence {stats['convergence_fraction']:.4f}  "
            f"max {stats['max_convergence']:.4f}",
            flush=True,
        )

    for cache in caches.values():
        cache.save()

    csv_path = RESULTS_DIR / f"isolation_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer_csv = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer_csv.writeheader()
        writer_csv.writerows(rows)

    table: list[dict[str, Any]] = []
    for persistence, inertia in product((True, False), (True, False)):
        cell = [
            r
            for r in rows
            if r["persistence_required"] == persistence and r["inertia_enabled"] == inertia
        ]
        entry: dict[str, Any] = {
            "seed": args.seed,
            "persistence_required": persistence,
            "inertia_enabled": inertia,
        }
        for field in (
            "convergence_fraction",
            "single_iteration_conclusion_rate",
            "mean_iterations_to_termination",
            "max_convergence",
        ):
            values = [float(r[field]) for r in cell]
            entry[f"{field}_mean"] = round(mean(values), 4)
            entry[f"{field}_sd"] = round(pstdev(values), 4) if len(values) > 1 else 0.0
        table.append(entry)

    def value(persistence: bool, inertia: bool) -> float:
        """Return one cell's convergence fraction."""
        for entry in table:
            if (
                entry["persistence_required"] == persistence
                and entry["inertia_enabled"] == inertia
            ):
                return float(entry["convergence_fraction_mean"])
        return 0.0

    persistence_effect = value(False, True) - value(True, True)
    inertia_effect = value(True, False) - value(True, True)

    if abs(inertia_effect) < 0.01 and persistence_effect > 0.05:
        verdict = "persistence_is_the_cause"
    elif abs(persistence_effect) < 0.01 and inertia_effect > 0.05:
        verdict = "inertia_is_the_cause"
    elif persistence_effect > 0.05 and inertia_effect > 0.05:
        verdict = "both_contribute"
    else:
        verdict = "neither_alone_explains_it"

    report = {
        "seed": args.seed,
        "seeds": seeds,
        "convergence_threshold": args.threshold,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "llm": args.llm,
        "cells": rows,
        "four_cell_table": table,
        "persistence_effect_on_convergence": round(persistence_effect, 4),
        "inertia_effect_on_convergence": round(inertia_effect, 4),
        "verdict": verdict,
    }
    (RESULTS_DIR / f"isolation_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print()
    header = (
        f"{'persistence':<13}{'inertia':<10}{'convergence':>16}"
        f"{'single iter':>15}{'mean iters':>14}{'max conv':>12}"
    )
    print(header)
    print("-" * len(header))
    for entry in table:
        print(
            f"{'on' if entry['persistence_required'] else 'off':<13}"
            f"{'on' if entry['inertia_enabled'] else 'off':<10}"
            f"{entry['convergence_fraction_mean']:>9.4f}+-{entry['convergence_fraction_sd']:<5.3f}"
            f"{entry['single_iteration_conclusion_rate_mean']:>9.4f}+-{entry['single_iteration_conclusion_rate_sd']:<4.3f}"
            f"{entry['mean_iterations_to_termination_mean']:>8.4f}+-{entry['mean_iterations_to_termination_sd']:<4.3f}"
            f"{entry['max_convergence_mean']:>12.4f}"
        )
    print()
    print(f"persistence effect on convergence {persistence_effect:+.4f}")
    print(f"inertia effect on convergence     {inertia_effect:+.4f}")
    print(f"VERDICT {verdict}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
