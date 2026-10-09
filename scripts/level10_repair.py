"""
Module: scripts/level10_repair.py

Runs the Level 10 repair experiment: stable hypothesis identity, all four
mechanisms on, three thresholds, five seeds.

What is being tested. L9 established that persistence is unsatisfiable
because generation replaces the hypothesis list every iteration and no named
hypothesis survives, so dominant_iterations never leaves zero. That
diagnosis is correlational. This experiment makes identity stable and asks
whether persistence then begins to gate convergence, which is the only way
to distinguish a mechanism that was correctly specified and incorrectly
coupled from one that would not work anyway.

Why it should be nearly free. The repair inherits only the identifier and
the dominant iteration counter. The description and the confidence stay
exactly as the model produced them, and the prompt the next iteration
assembles prints only descriptions and confidences, so every prompt this run
issues is byte identical to one the Level 9 all on cells already issued and
paid for. Early termination can only shorten an analysis, so the prompts
issued are a prefix of the baseline's. The expectation is therefore close to
a hundred per cent cache hits and close to zero new model calls, and the
pilot is there to check that before the full grid runs.

The baseline is not re-run. The matching all on cells at each threshold and
seed already exist in results/ablation from Level 9.
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
from itertools import product
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / "Enigma-AIAgent" / ".env")

sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from enigma_reason.config import settings  # noqa: E402
from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.graph.nodes import IDENTITY_MATCH_THRESHOLD  # noqa: E402
from enigma_reason.graph.runner import _default_llm_factory  # noqa: E402
from enigma_reason.observability.llm_cache import CachingLLMFactory, ResponseCache  # noqa: E402
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter, text_hash  # noqa: E402
from enigma_reason.replay.concurrent import ConcurrentReplay  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402
from scenarios.generator import suite_hash  # noqa: E402

from level7_validate import load_suite  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
RESULTS_DIR = PROJECT_ROOT / "results" / "repair"

INPUT_USD_PER_MILLION = 0.30
OUTPUT_USD_PER_MILLION = 2.50
MEAN_PROMPT_TOKENS = 340.0
MEAN_COMPLETION_TOKENS = 99.0
SECONDS_PER_CALL = 8.927

WALL_CLOCK_LIMIT_MINUTES = 30.0
COST_LIMIT_USD = 2.00


def threshold_tag(threshold: float) -> str:
    """Return the filename fragment for a threshold."""
    return f"t{int(round(threshold * 100)):03d}"


def estimate(calls: int, concurrency: int) -> dict[str, Any]:
    """Price a number of uncached model calls."""
    input_usd = calls * MEAN_PROMPT_TOKENS / 1_000_000 * INPUT_USD_PER_MILLION
    output_usd = calls * MEAN_COMPLETION_TOKENS / 1_000_000 * OUTPUT_USD_PER_MILLION
    seconds = calls * SECONDS_PER_CALL / max(concurrency, 1)
    return {
        "uncached_calls": calls,
        "input_tokens": round(calls * MEAN_PROMPT_TOKENS),
        "output_tokens": round(calls * MEAN_COMPLETION_TOKENS),
        "input_usd": round(input_usd, 4),
        "output_usd": round(output_usd, 4),
        "total_usd": round(input_usd + output_usd, 4),
        "wall_clock_seconds": round(seconds, 1),
        "wall_clock_minutes": round(seconds / 60, 2),
    }


def main() -> int:
    """Run the pilot, apply the budget gate, then the grid if it passes."""
    parser = argparse.ArgumentParser(description="Level 10 repair experiment.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=str, default="42,123,456,789,1024")
    parser.add_argument("--thresholds", type=str, default="0.30,0.50,0.80")
    parser.add_argument("--concurrency", type=int, default=40)
    parser.add_argument("--pilot-units", type=int, default=20)
    parser.add_argument("--stage", choices=("pilot", "full"), default="pilot")
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
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

    calls_per_pass = sum(3 * len(s.signals) for s in scenarios)
    total_if_all_missed = calls_per_pass * len(thresholds) * len(seeds)
    prior_hit_rate = 0.9911
    prior_estimate = estimate(
        round(total_if_all_missed * (1 - prior_hit_rate)), args.concurrency
    )

    print(f"seed {args.seed}   suite {suite_path.name}   hash {digest}")
    print(f"thresholds {thresholds}   seeds {seeds}   scenarios {len(scenarios)}")
    print(f"units {len(thresholds) * len(seeds) * len(scenarios)}")
    print(f"identity match rule: normalised SequenceMatcher, threshold "
          f"{IDENTITY_MATCH_THRESHOLD}, greedy one to one, fixed before the run")
    print()
    print("PRIOR ESTIMATE from the L9 measured hit rate of 0.9911")
    print(f"  calls if every one missed   {total_if_all_missed}")
    print(f"  expected uncached calls     {prior_estimate['uncached_calls']}")
    print(f"  expected wall clock         {prior_estimate['wall_clock_minutes']} min")
    print(f"  expected cost               ${prior_estimate['total_usd']}")
    print(f"  pricing                     ${INPUT_USD_PER_MILLION}/M in, "
          f"${OUTPUT_USD_PER_MILLION}/M out, published Gemini 2.5 Flash paid tier")
    print(f"  token means                 {MEAN_PROMPT_TOKENS:.0f} prompt, "
          f"{MEAN_COMPLETION_TOKENS:.0f} completion, measured offline")
    print(flush=True)

    caches: dict[int, ResponseCache] = {}
    factories: dict[int, Any] = {}
    for seed in seeds:
        cache_path = RESULTS_DIR / f"cache_seed{seed}.json"
        warm = ABLATION_DIR / f"cache_seed{seed}.json"
        if not cache_path.exists() and warm.exists():
            shutil.copy2(warm, cache_path)
        cache = ResponseCache(cache_path, model=settings.gemini_model)
        caches[seed] = cache
        factories[seed] = CachingLLMFactory(_default_llm_factory, cache)

    writers: dict[tuple[float, int], RunLogWriter] = {}
    entities: dict[tuple[float, int], dict[str, str]] = {}
    descriptions: dict[tuple[float, int], dict[str, str]] = {}
    paths: dict[tuple[float, int], Path] = {}
    suffix = "pilot" if args.stage == "pilot" else "full"
    for threshold, seed in product(thresholds, seeds):
        key = (threshold, seed)
        path = RESULTS_DIR / f"repair_{threshold_tag(threshold)}_{seed}_{suffix}.jsonl"
        if path.exists():
            path.unlink()
        paths[key] = path
        writer = RunLogWriter(path)
        writer.__enter__()
        writers[key] = writer
        entities[key] = {}
        descriptions[key] = {}

    units: list[tuple[str, Any]] = []
    for threshold, seed in product(thresholds, seeds):
        for scenario in scenarios:
            units.append((f"{threshold}|{seed}|{scenario.scenario_id}", scenario.signals))
    if args.stage == "pilot":
        units = units[: args.pilot_units]

    def build_replay(unit: str, _factory):
        """Create the repaired replay for one threshold, seed and scenario."""
        threshold_text, seed_text, _ = unit.split("|")
        threshold = float(threshold_text)
        seed = int(seed_text)
        key = (threshold, seed)

        def harvest(situation, final_state) -> None:
            """Record hypothesis text and the entity a situation belongs to."""
            for hypothesis in final_state.get("hypotheses", []):
                description = str(hypothesis.get("description", ""))
                descriptions[key][text_hash(description)] = description
            evidence = situation.evidence
            if evidence and evidence[0].entity:
                entities[key][str(situation.situation_id)] = str(evidence[0].entity)

        return OfflineReplay(
            factories[seed],
            run_log=writers[key],
            seed=seed,
            correlation=EntityCorrelation(),
            on_analysis=harvest,
            controls=EpistemicControls(stable_hypothesis_identity=True),
            convergence_threshold=threshold,
        )

    driver = ConcurrentReplay(
        build_replay, lambda: None, concurrency=args.concurrency, run_log=None
    )
    run_started = time.monotonic()
    outcome = driver.run(units)
    elapsed = time.monotonic() - run_started

    for writer in writers.values():
        writer.flush()
        writer.__exit__(None, None, None)
    for cache in caches.values():
        cache.save()

    hits = sum(c.stats.hits for c in caches.values())
    misses = sum(c.stats.misses for c in caches.values())
    lookups = hits + misses
    realised_hit_rate = hits / lookups if lookups else 0.0
    realised = estimate(misses, args.concurrency)
    realised["wall_clock_seconds"] = round(elapsed, 1)
    realised["wall_clock_minutes"] = round(elapsed / 60, 2)

    projection = None
    if args.stage == "pilot" and units:
        scale = (len(thresholds) * len(seeds) * len(scenarios)) / len(units)
        projection = estimate(round(misses * scale), args.concurrency)
        projection["scale_factor"] = round(scale, 2)
        projection["basis"] = "pilot measured miss count, scaled to the full grid"
        projection["within_wall_clock_limit"] = bool(
            projection["wall_clock_minutes"] <= WALL_CLOCK_LIMIT_MINUTES
        )
        projection["within_cost_limit"] = bool(
            projection["total_usd"] <= COST_LIMIT_USD
        )
        projection["gate_passes"] = bool(
            projection["within_wall_clock_limit"] and projection["within_cost_limit"]
        )

    report = {
        "seed": args.seed,
        "stage": args.stage,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "suite_hash": digest,
        "thresholds": thresholds,
        "seeds": seeds,
        "scenarios": len(scenarios),
        "units_run": len(units),
        "units_failed": outcome.units_failed,
        "retries": len(outcome.retries),
        "concurrency": args.concurrency,
        "model_name": settings.gemini_model,
        "identity_match_rule": (
            "normalise to lowercase alphanumeric words, difflib SequenceMatcher "
            "ratio, greedy one to one assignment in descending similarity, "
            "UNKNOWN and pruned hypotheses excluded"
        ),
        "identity_match_threshold": IDENTITY_MATCH_THRESHOLD,
        "threshold_fixed_before_run": True,
        "pricing": {
            "input_usd_per_million": INPUT_USD_PER_MILLION,
            "output_usd_per_million": OUTPUT_USD_PER_MILLION,
            "source": "published Gemini 2.5 Flash paid tier, standard",
            "mean_prompt_tokens": MEAN_PROMPT_TOKENS,
            "mean_completion_tokens": MEAN_COMPLETION_TOKENS,
        },
        "prior_estimate": prior_estimate,
        "cache": {
            "hits": hits,
            "misses": misses,
            "lookups": lookups,
            "hit_rate": round(realised_hit_rate, 6),
        },
        "realised": realised,
        "projection_to_full_grid": projection,
        "limits": {
            "wall_clock_minutes": WALL_CLOCK_LIMIT_MINUTES,
            "cost_usd": COST_LIMIT_USD,
        },
    }
    (RESULTS_DIR / f"budget_{args.stage}_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    for (threshold, seed), path in paths.items():
        base = path.with_suffix("")
        base.with_name(base.name + "_entities.json").write_text(
            json.dumps(entities[(threshold, seed)], indent=2), encoding="utf-8"
        )
        base.with_name(base.name + "_descriptions.json").write_text(
            json.dumps(descriptions[(threshold, seed)], indent=2), encoding="utf-8"
        )

    if args.stage == "full":
        manifest = build_run_manifest(
            experiment="level10_repair",
            seed=args.seed,
            config={
                "suite": str(suite_path.relative_to(PROJECT_ROOT)),
                "suite_hash": digest,
                "thresholds": thresholds,
                "seeds": seeds,
                "identity_match_threshold": IDENTITY_MATCH_THRESHOLD,
                "identity_match_rule": report["identity_match_rule"],
                "stable_hypothesis_identity": True,
            },
            started_at=started,
            project_root=PROJECT_ROOT,
            dataset=suite_path,
            extra={"cache": report["cache"], "realised": realised},
        )
        write_manifest(manifest, RESULTS_DIR / f"manifest_seed{args.seed}.json")

    print(f"stage {args.stage}   units run {len(units)}   failed {outcome.units_failed}"
          f"   retries {len(outcome.retries)}")
    print(f"cache hits {hits}  misses {misses}  hit rate {realised_hit_rate:.6f}")
    print(f"REALISED  {realised['wall_clock_minutes']} min   ${realised['total_usd']}")
    if projection:
        print()
        print(f"PROJECTION to the full grid, scale {projection['scale_factor']}x")
        print(f"  uncached calls   {projection['uncached_calls']}")
        print(f"  wall clock       {projection['wall_clock_minutes']} min "
              f"(limit {WALL_CLOCK_LIMIT_MINUTES})")
        print(f"  cost             ${projection['total_usd']} "
              f"(limit ${COST_LIMIT_USD})")
        print(f"  GATE {'PASSES' if projection['gate_passes'] else 'FAILS'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
