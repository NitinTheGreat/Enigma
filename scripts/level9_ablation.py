"""
Module: scripts/level9_ablation.py

Runs the Level 9 factorial: sixteen epistemic configurations by three
convergence thresholds by five seeds over the frozen sub-suite.

Scheduling. All 9600 units are put into one pool, because L7.9.8 measured
that a unit runs on one worker and wall clock is floored by the longest unit,
so feeding the driver one cell at a time would pay that floor 240 times.

Checkpointing. This is the longest job the project has run and a crash must
not cost it. Every finished unit appends a line to a checkpoint file, and a
restart skips units already recorded there. Run logs are opened in append
mode and never truncated, so a resumed run continues its cells rather than
replacing them. The response caches are flushed on a timer as well as at the
end, so paid model calls survive an interruption too.

The caches are seeded from the clock study rather than started cold. Level 8
ran the all on configuration at the standing 0.8 threshold in separated mode,
which is exactly one of the 240 cells here, and every prompt it paid for is
reusable by the configurations that do not change a prompt.

Caches are scoped per seed, as in Level 8, so the five replicates stay
independent draws rather than four replays of the first.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from itertools import combinations, product
from pathlib import Path
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
from scenarios.generator import suite_hash  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
CLOCK_DIR = PROJECT_ROOT / "results" / "clock_study"
RESULTS_DIR = PROJECT_ROOT / "results" / "ablation"

SWITCHES = ("U", "S", "A", "P")
INERTIA_OFF = 1e9


def configuration_name(ablated: str) -> str:
    """Return the stable cell name for a set of disabled switches."""
    return ablated if ablated else "allon"


def controls_for(ablated: str, inertia_off: bool = False) -> EpistemicControls:
    """Build the control set with the named switches removed."""
    return EpistemicControls(
        unknown_hypothesis_enabled="U" not in ablated,
        sanity_gate_enabled="S" not in ablated,
        asymmetric_decay_enabled="A" not in ablated,
        persistence_required="P" not in ablated,
        max_confidence_delta=INERTIA_OFF if inertia_off else 0.15,
    )


def threshold_tag(threshold: float) -> str:
    """Return the filename fragment for a threshold."""
    return f"t{int(round(threshold * 100)):03d}"


def main() -> int:
    """Run the factorial, resuming from any checkpoint already present."""
    parser = argparse.ArgumentParser(description="Level 9 epistemic ablation.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--thresholds", type=str, default="0.30,0.50,0.80")
    parser.add_argument("--concurrency", type=int, default=40)
    parser.add_argument("--llm", choices=("real", "mock"), default="real")
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    parser.add_argument("--progress-seconds", type=float, default=120.0)
    parser.add_argument("--limit-configurations", type=int, default=0)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    digest = suite_hash(scenarios)

    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    thresholds = [float(t) for t in args.thresholds.split(",") if t.strip()]
    ablations = [
        "".join(c)
        for n in range(len(SWITCHES) + 1)
        for c in combinations(SWITCHES, n)
    ]
    if args.limit_configurations:
        ablations = ablations[: args.limit_configurations]

    checkpoint_path = RESULTS_DIR / f"checkpoint_seed{args.seed}.jsonl"
    done: set[str] = set()
    if checkpoint_path.exists():
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(line.strip())

    caches: dict[int, ResponseCache] = {}
    factories: dict[int, Any] = {}
    for seed in seeds:
        if args.llm == "mock":
            factories[seed] = mock_llm_factory(seed=seed)
            continue
        cache_path = RESULTS_DIR / f"cache_seed{seed}.json"
        warm = CLOCK_DIR / f"cache_seed{seed}.json"
        if not cache_path.exists() and warm.exists():
            shutil.copy2(warm, cache_path)
        cache = ResponseCache(cache_path, model=settings.gemini_model)
        caches[seed] = cache
        factories[seed] = CachingLLMFactory(_default_llm_factory, cache)

    warm_entries = sum(len(c) for c in caches.values()) if caches else 0

    writers: dict[tuple[str, float, int], RunLogWriter] = {}
    descriptions: dict[tuple[str, float, int], dict[str, str]] = {}
    entities: dict[tuple[str, float, int], dict[str, str]] = {}
    log_paths: dict[tuple[str, float, int], Path] = {}
    for ablated, threshold, seed in product(ablations, thresholds, seeds):
        key = (ablated, threshold, seed)
        name = f"{configuration_name(ablated)}_{threshold_tag(threshold)}_{seed}"
        path = RESULTS_DIR / f"{name}.jsonl"
        log_paths[key] = path
        writers[key] = RunLogWriter(path)
        writers[key].__enter__()
        descriptions[key] = {}
        entities[key] = {}

    by_id = {s.scenario_id: s for s in scenarios}
    calls_per_scenario = {s.scenario_id: 3 * len(s.signals) for s in scenarios}
    longest_unit = max(calls_per_scenario.values())
    predicted_critical_path = longest_unit * 8.927

    units: list[tuple[str, Any]] = []
    skipped = 0
    for ablated, threshold, seed in product(ablations, thresholds, seeds):
        for scenario in scenarios:
            unit = f"{configuration_name(ablated)}|{threshold}|{seed}|{scenario.scenario_id}"
            if unit in done:
                skipped += 1
                continue
            units.append((unit, scenario.signals))

    total_units = len(ablations) * len(thresholds) * len(seeds) * len(scenarios)

    print(f"seed {args.seed}   suite {suite_path.name}   hash {digest}")
    print(f"configurations {len(ablations)}   thresholds {thresholds}   seeds {seeds}")
    print(f"units total {total_units}   already done {skipped}   to run {len(units)}")
    print(f"warm cache entries {warm_entries}")
    print(f"longest unit {longest_unit} calls")
    print(f"PREDICTED critical path {predicted_critical_path:.0f} s "
          f"({predicted_critical_path / 60:.1f} min)")
    print(f"concurrency {args.concurrency}   model {args.llm}")
    print(flush=True)

    checkpoint_lock = threading.Lock()
    checkpoint_handle = checkpoint_path.open("a", encoding="utf-8")
    completed = {"count": 0}

    def record_done(unit: str) -> None:
        """Append one finished unit to the checkpoint."""
        with checkpoint_lock:
            checkpoint_handle.write(unit + "\n")
            checkpoint_handle.flush()
            completed["count"] += 1

    def build_replay(unit: str, _factory):
        """Create the replay for one configuration, threshold, seed and scenario."""
        name, threshold_text, seed_text, _ = unit.split("|")
        threshold = float(threshold_text)
        seed = int(seed_text)
        ablated = "" if name == "allon" else name
        key = (ablated, threshold, seed)

        def harvest(situation, final_state) -> None:
            """Record hypothesis text and the entity a situation belongs to."""
            for hypothesis in final_state.get("hypotheses", []):
                description = str(hypothesis.get("description", ""))
                descriptions[key][text_hash(description)] = description
            evidence = situation.evidence
            if evidence and evidence[0].entity:
                entities[key][str(situation.situation_id)] = str(evidence[0].entity)

        replay = OfflineReplay(
            factories[seed],
            run_log=writers[key],
            seed=seed,
            correlation=EntityCorrelation(),
            on_analysis=harvest,
            controls=controls_for(ablated),
            convergence_threshold=threshold,
        )
        original_run = replay.run

        def run_and_checkpoint(signals):
            """Run the unit then mark it done, so a restart skips it."""
            outcome = original_run(signals)
            record_done(unit)
            return outcome

        replay.run = run_and_checkpoint
        return replay

    stop_reporting = threading.Event()
    run_started = time.monotonic()

    def report_progress() -> None:
        """Print progress and flush caches while the run is going."""
        while not stop_reporting.wait(args.progress_seconds):
            for cache in caches.values():
                cache.save()
            elapsed = time.monotonic() - run_started
            finished = completed["count"]
            rate = finished / elapsed if elapsed else 0.0
            remaining = (len(units) - finished) / rate if rate else 0.0
            hits = sum(c.stats.hits for c in caches.values())
            misses = sum(c.stats.misses for c in caches.values())
            lookups = hits + misses
            print(
                f"[progress] units {finished}/{len(units)} "
                f"({100 * finished / max(len(units), 1):.1f}%)  "
                f"elapsed {elapsed / 3600:.2f} h  "
                f"eta {remaining / 3600:.2f} h  "
                f"cache {hits}/{lookups} "
                f"({hits / lookups if lookups else 0:.4f})",
                flush=True,
            )

    reporter = threading.Thread(target=report_progress, daemon=True)
    reporter.start()

    driver = ConcurrentReplay(
        build_replay,
        lambda: None,
        concurrency=args.concurrency,
        run_log=None,
    )

    try:
        outcome = driver.run(units)
    finally:
        stop_reporting.set()
        for cache in caches.values():
            cache.save()
        checkpoint_handle.close()
    elapsed = time.monotonic() - run_started

    for writer in writers.values():
        writer.flush()
        writer.__exit__(None, None, None)

    hits = sum(c.stats.hits for c in caches.values())
    misses = sum(c.stats.misses for c in caches.values())
    lookups = hits + misses

    index_rows = []
    for (ablated, threshold, seed), path in sorted(log_paths.items()):
        index_rows.append(
            {
                "seed": seed,
                "configuration": configuration_name(ablated),
                "ablated": ablated or "none",
                "unknown_enabled": "U" not in ablated,
                "sanity_gate_enabled": "S" not in ablated,
                "asymmetric_decay_enabled": "A" not in ablated,
                "persistence_required": "P" not in ablated,
                "convergence_threshold": threshold,
                "run_log": str(path.relative_to(PROJECT_ROOT)),
                "records": sum(1 for _ in path.open(encoding="utf-8")) if path.exists() else 0,
            }
        )
        entity_path = path.with_name(path.stem + "_entities.json")
        entity_path.write_text(
            json.dumps(entities[(ablated, threshold, seed)], indent=2), encoding="utf-8"
        )
        description_path = path.with_name(path.stem + "_descriptions.json")
        description_path.write_text(
            json.dumps(descriptions[(ablated, threshold, seed)], indent=2),
            encoding="utf-8",
        )

    index_path = RESULTS_DIR / f"cells_index_seed{args.seed}.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer_csv = csv.DictWriter(handle, fieldnames=list(index_rows[0].keys()))
        writer_csv.writeheader()
        writer_csv.writerows(index_rows)

    report = {
        "seed": args.seed,
        "seeds": seeds,
        "thresholds": thresholds,
        "configurations": ablations,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "suite_hash": digest,
        "scenarios": len(scenarios),
        "units_total": total_units,
        "units_skipped_from_checkpoint": skipped,
        "units_run": len(units),
        "units_failed": outcome.units_failed,
        "retries": len(outcome.retries),
        "concurrency": args.concurrency,
        "llm": args.llm,
        "model_name": settings.gemini_model if args.llm == "real" else "mock",
        "cache_scope": "one cache per seed, seeded from the clock study",
        "cache_warm_entries_at_start": warm_entries,
        "cache": {
            "hits": hits,
            "misses": misses,
            "lookups": lookups,
            "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
        },
        "predicted_critical_path_seconds": round(predicted_critical_path, 1),
        "actual_wall_clock_seconds": round(elapsed, 1),
        "actual_wall_clock_hours": round(elapsed / 3600, 3),
        "started_at_utc": started.isoformat(),
    }
    (RESULTS_DIR / f"run_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    manifest = build_run_manifest(
        experiment="level9_ablation",
        seed=args.seed,
        config={
            "suite": str(suite_path.relative_to(PROJECT_ROOT)),
            "suite_hash": digest,
            "configurations": ablations,
            "thresholds": thresholds,
            "seeds": seeds,
            "concurrency": args.concurrency,
            "model_name": settings.gemini_model if args.llm == "real" else "mock",
        },
        started_at=started,
        project_root=PROJECT_ROOT,
        dataset=suite_path,
        extra={"units": total_units, "cache": report["cache"]},
    )
    write_manifest(manifest, RESULTS_DIR / f"manifest_seed{args.seed}.json")

    print()
    print(f"ACTUAL wall clock {elapsed:.0f} s ({elapsed / 3600:.2f} h)")
    print(f"  predicted critical path {predicted_critical_path:.0f} s, "
          f"ratio {elapsed / predicted_critical_path:.2f}")
    print(f"units run {len(units)}   failed {outcome.units_failed}   "
          f"retries {len(outcome.retries)}")
    print(f"cache hits {hits} misses {misses} hit rate "
          f"{hits / lookups if lookups else 0:.4f}")
    print(f"written {index_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
