"""
Module: scripts/level8_clock_study.py

Runs the clock domain study across the full cross product of its grid.

Scheduling. The grid is three clock modes by five seeds by forty scenarios,
which is 600 units. L7.9.8 measured that a unit runs on one worker and that
wall clock is floored by the longest unit, so feeding the driver one pass at
a time pays that floor fifteen times and makes concurrency stop binding. All
600 units are therefore scheduled as one pool, which is the difference
between 12.16 hours and 6.31 hours in the budget and is the whole reason the
cross product matters.

Caches are scoped per seed, not shared across the grid. This resolves a
tension in the brief. The prompt a situation assembles does not depend on the
seed, so a cache shared across seeds would serve seed one's responses to
every later seed, every replicate would be identical, and the standard
deviation across five seeds would be exactly zero by construction rather than
because the model is stable. Scoping per seed keeps the cache doing its job
within a seed while leaving the five replicates genuinely independent draws
from a model sampling at temperature 0.2.

Outputs follow the build plan: one run log per mode and seed at
results/clock_study/{mode}_{seed}.jsonl, plus a summary and a per
configuration CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter, text_hash  # noqa: E402
from enigma_reason.replay.concurrent import ConcurrentReplay  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay, mock_llm_factory  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402
from scenarios.generator import Regime, suite_hash  # noqa: E402
from scenarios.scoring import score_run  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "clock_study"

MODES = ("conflated", "wall", "separated")
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


def log_statistics(path: Path, threshold: float) -> dict[str, Any]:
    """Summarise the temporal and belief quantities one run log carries."""
    trends: Counter[str] = Counter()
    quiet = 0
    burst = 0
    records = 0
    terminal = 0
    converged = 0
    unknown_final: list[float] = []
    iterations_final: list[int] = []
    max_convergence = 0.0

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        if record.get("record_type") == "retry":
            continue
        records += 1
        trends[str(record.get("trend", "unknown"))] += 1
        if record.get("is_quiet"):
            quiet += 1
        if record.get("burst_detected"):
            burst += 1
        score = float(record.get("convergence_score") or 0.0)
        max_convergence = max(max_convergence, score)
        if record.get("terminated"):
            terminal += 1
            iterations_final.append(int(record.get("iteration") or 0))
            if score >= threshold:
                converged += 1
            for hypothesis in record.get("hypotheses", []):
                if hypothesis.get("is_unknown"):
                    unknown_final.append(float(hypothesis.get("confidence") or 0.0))
                    break

    return {
        "iteration_records": records,
        "trend_distribution": dict(sorted(trends.items())),
        "trend_labels_seen": len(trends),
        "quiet_fraction": round(quiet / records, 4) if records else 0.0,
        "burst_fraction": round(burst / records, 4) if records else 0.0,
        "analyses_terminated": terminal,
        "convergence_fraction": round(converged / terminal, 4) if terminal else 0.0,
        "max_convergence": round(max_convergence, 4),
        "mean_final_unknown_confidence": round(mean(unknown_final), 4)
        if unknown_final
        else 0.0,
        "mean_iterations_to_termination": round(mean(iterations_final), 4)
        if iterations_final
        else 0.0,
    }


def main() -> int:
    """Run the three clock modes at five seeds over the frozen sub-suite."""
    parser = argparse.ArgumentParser(description="Level 8 clock domain study.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--modes", type=str, default=",".join(MODES))
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--llm", choices=("real", "mock"), default="real")
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    parser.add_argument("--tag", type=str, default="")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    digest = suite_hash(scenarios)

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    calls_per_scenario = {s.scenario_id: 3 * len(s.signals) for s in scenarios}
    longest_unit = max(calls_per_scenario.values())
    total_calls = sum(calls_per_scenario.values()) * len(modes) * len(seeds)
    predicted_critical_path = longest_unit * 8.927
    predicted_by_concurrency = total_calls * 8.927 / args.concurrency

    print(f"seed {args.seed}   suite {suite_path.name}   hash {digest}")
    print(f"modes {modes}   seeds {seeds}   scenarios {len(scenarios)}")
    print(f"units {len(modes) * len(seeds) * len(scenarios)}")
    print(f"model calls if every one misses {total_calls}")
    print(f"longest unit {longest_unit} calls")
    print(
        f"PREDICTED critical path {predicted_critical_path:.0f} s "
        f"({predicted_critical_path / 60:.1f} min)"
    )
    print(
        f"PREDICTED work over concurrency {predicted_by_concurrency:.0f} s "
        f"({predicted_by_concurrency / 3600:.2f} h) at concurrency {args.concurrency}"
    )
    print()

    caches: dict[int, ResponseCache] = {}
    factories: dict[int, Any] = {}
    for seed in seeds:
        if args.llm == "mock":
            factories[seed] = mock_llm_factory(seed=seed)
            continue
        cache_path = RESULTS_DIR / f"cache_seed{seed}.json"
        cache = ResponseCache(cache_path, model=settings.gemini_model)
        caches[seed] = cache
        factories[seed] = CachingLLMFactory(_default_llm_factory, cache)

    writers: dict[tuple[str, int], RunLogWriter] = {}
    descriptions: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    entities: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    log_paths: dict[tuple[str, int], Path] = {}

    for mode in modes:
        for seed in seeds:
            path = RESULTS_DIR / f"{mode}_{seed}.jsonl"
            if path.exists():
                path.unlink()
            log_paths[(mode, seed)] = path
            writers[(mode, seed)] = RunLogWriter(path)
            writers[(mode, seed)].__enter__()

    controls = EpistemicControls()
    by_id = {s.scenario_id: s for s in scenarios}

    def build_replay(unit: str, unit_factory):
        """Create the replay for one mode, seed and scenario triple."""
        mode, seed_text, _ = unit.split("|")
        seed = int(seed_text)
        key = (mode, seed)

        def harvest(situation, final_state) -> None:
            """Record hypothesis text and the entity a situation belongs to."""
            for hypothesis in final_state.get("hypotheses", []):
                description = str(hypothesis.get("description", ""))
                descriptions[key][text_hash(description)] = description
            evidence = situation.evidence
            if evidence and evidence[0].entity:
                entities[key][str(situation.situation_id)] = str(evidence[0].entity)

        return OfflineReplay(
            unit_factory,
            run_log=writers[key],
            seed=seed,
            clock_mode=mode,
            correlation=EntityCorrelation(),
            on_analysis=harvest,
            controls=controls,
        )

    units: list[tuple[str, Any]] = []
    for mode in modes:
        for seed in seeds:
            for scenario in scenarios:
                units.append(
                    (f"{mode}|{seed}|{scenario.scenario_id}", scenario.signals)
                )

    def factory_for_unit(unit: str):
        """Return the seed scoped factory this unit must use."""
        seed = int(unit.split("|")[1])
        return factories[seed]

    driver = ConcurrentReplay(
        lambda unit, _factory: build_replay(unit, factory_for_unit(unit)),
        lambda: None,
        concurrency=args.concurrency,
        run_log=None,
    )

    stop_saving = threading.Event()

    def persist_caches() -> None:
        """Flush every cache to disk while the run is still going.

        A run of this length must not hold hours of paid responses only in
        memory. Saving periodically means an interruption costs the units in
        flight rather than everything bought so far.
        """
        while not stop_saving.wait(60.0):
            for saved in caches.values():
                saved.save()

    saver = threading.Thread(target=persist_caches, daemon=True)
    saver.start()

    run_started = time.monotonic()
    try:
        outcome = driver.run(units)
    finally:
        stop_saving.set()
        for cache in caches.values():
            cache.save()
    elapsed = time.monotonic() - run_started

    for writer in writers.values():
        writer.flush()
        writer.__exit__(None, None, None)
    for cache in caches.values():
        cache.save()

    cache_totals = {"hits": 0, "misses": 0, "writes": 0, "lookups": 0}
    for cache in caches.values():
        stats = cache.stats.to_dict()
        for key_name in cache_totals:
            cache_totals[key_name] += stats.get(key_name, 0)
    hit_rate = (
        cache_totals["hits"] / cache_totals["lookups"] if cache_totals["lookups"] else 0.0
    )

    threshold = settings.graph_convergence_threshold
    cells: list[dict[str, Any]] = []
    for mode in modes:
        for seed in seeds:
            key = (mode, seed)
            path = log_paths[key]
            stats = log_statistics(path, threshold)
            outcomes, overall, per_regime = score_run(
                path, scenarios, entities[key], descriptions[key]
            )
            outcomes_path = RESULTS_DIR / f"outcomes_{mode}_{seed}.jsonl"
            with outcomes_path.open("w", encoding="utf-8") as handle:
                for item in outcomes:
                    handle.write(json.dumps(item.to_dict(), separators=(",", ":")) + chr(10))
            entity_path = RESULTS_DIR / f"entities_{mode}_{seed}.json"
            entity_path.write_text(
                json.dumps(entities[key], indent=2), encoding="utf-8"
            )
            row: dict[str, Any] = {
                "seed": seed,
                "clock_mode": mode,
                "situations_scored": overall.situations,
                **stats,
            }
            for metric in METRIC_NAMES:
                row[metric] = getattr(overall, metric)
            row["per_regime"] = {k: v.to_dict() for k, v in per_regime.items()}
            cells.append(row)

    csv_path = RESULTS_DIR / f"cells_seed{args.seed}.csv"
    flat_fields = [k for k in cells[0] if k not in ("per_regime", "trend_distribution")]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer_csv = csv.DictWriter(
            handle, fieldnames=flat_fields + ["trend_distribution"]
        )
        writer_csv.writeheader()
        for row in cells:
            flat = {k: row[k] for k in flat_fields}
            flat["trend_distribution"] = json.dumps(row["trend_distribution"])
            writer_csv.writerow(flat)

    def summarise(mode: str) -> dict[str, Any]:
        """Aggregate the five seeds of one mode with mean and deviation."""
        rows = [c for c in cells if c["clock_mode"] == mode]
        summary: dict[str, Any] = {"clock_mode": mode, "seeds": len(rows)}
        numeric = [
            "quiet_fraction",
            "burst_fraction",
            "convergence_fraction",
            "max_convergence",
            "mean_final_unknown_confidence",
            "mean_iterations_to_termination",
            "trend_labels_seen",
            *METRIC_NAMES,
        ]
        for field in numeric:
            values = [float(r[field]) for r in rows]
            summary[f"{field}_mean"] = round(mean(values), 4)
            summary[f"{field}_sd"] = round(pstdev(values), 4) if len(values) > 1 else 0.0
        pooled: Counter[str] = Counter()
        for row in rows:
            pooled.update(row["trend_distribution"])
        total = sum(pooled.values())
        summary["trend_distribution_pooled"] = dict(sorted(pooled.items()))
        summary["trend_distribution_share"] = {
            k: round(v / total, 4) for k, v in sorted(pooled.items())
        }
        return summary

    summaries = [summarise(mode) for mode in modes]

    summary_csv = RESULTS_DIR / f"summary_seed{args.seed}.csv"
    summary_fields = [k for k in summaries[0] if not isinstance(summaries[0][k], dict)]
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer_csv = csv.DictWriter(handle, fieldnames=summary_fields)
        writer_csv.writeheader()
        for row in summaries:
            writer_csv.writerow({k: row[k] for k in summary_fields})

    report = {
        "seed": args.seed,
        "seeds": seeds,
        "modes": modes,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "suite_hash": digest,
        "scenarios": len(scenarios),
        "units": len(units),
        "llm": args.llm,
        "model_name": settings.gemini_model if args.llm == "real" else "mock",
        "concurrency": args.concurrency,
        "cache_scope": "one cache per seed, not shared across seeds",
        "cache": {**cache_totals, "hit_rate": round(hit_rate, 4)},
        "predicted_critical_path_seconds": round(predicted_critical_path, 1),
        "predicted_work_over_concurrency_seconds": round(predicted_by_concurrency, 1),
        "actual_wall_clock_seconds": round(elapsed, 1),
        "actual_wall_clock_hours": round(elapsed / 3600, 3),
        "units_failed": outcome.units_failed,
        "retries": len(outcome.retries),
        "analyses_run": outcome.analyses_run,
        "convergence_threshold": threshold,
        "cells": cells,
        "summaries": summaries,
    }
    (RESULTS_DIR / f"study_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    manifest = build_run_manifest(
        experiment="level8_clock_study",
        seed=args.seed,
        config={
            "suite": str(suite_path.relative_to(PROJECT_ROOT)),
            "suite_hash": digest,
            "modes": modes,
            "seeds": seeds,
            "concurrency": args.concurrency,
            "llm": args.llm,
            "model_name": settings.gemini_model if args.llm == "real" else "mock",
        },
        started_at=started,
        project_root=PROJECT_ROOT,
        dataset=suite_path,
        extra={
            "units": len(units),
            "cache": report["cache"],
            "wall_clock_seconds": report["actual_wall_clock_seconds"],
        },
    )
    write_manifest(manifest, RESULTS_DIR / f"manifest_seed{args.seed}.json")

    print(f"ACTUAL wall clock {elapsed:.0f} s ({elapsed / 3600:.2f} h)")
    print(
        f"  against predicted critical path {predicted_critical_path:.0f} s, "
        f"ratio {elapsed / predicted_critical_path:.2f}"
    )
    print(f"units failed {outcome.units_failed}   retries {len(outcome.retries)}")
    print(
        f"cache hits {cache_totals['hits']} misses {cache_totals['misses']} "
        f"hit rate {hit_rate:.4f}"
    )
    print()
    header = (
        f"{'mode':<11}{'trends':>7}{'quiet':>8}{'conv':>7}{'unkC':>8}"
        f"{'iters':>7}{'correct':>9}{'false':>8}{'abst':>8}"
    )
    print(header)
    print("-" * len(header))
    for row in summaries:
        print(
            f"{row['clock_mode']:<11}{row['trend_labels_seen_mean']:>7}"
            f"{row['quiet_fraction_mean']:>8}{row['convergence_fraction_mean']:>7}"
            f"{row['mean_final_unknown_confidence_mean']:>8}"
            f"{row['mean_iterations_to_termination_mean']:>7}"
            f"{row['correct_conclusion_rate_mean']:>9}"
            f"{row['false_conclusion_rate_mean']:>8}"
            f"{row['abstention_rate_mean']:>8}"
        )
    print()
    for row in summaries:
        print(f"{row['clock_mode']:<11} trends {json.dumps(row['trend_distribution_share'])}")
    print()
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"written {summary_csv.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
