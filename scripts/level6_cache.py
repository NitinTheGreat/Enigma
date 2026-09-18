"""
Module: scripts/level6_cache.py

Measures how much of the Level 9 model spend the response cache removes.

Three measurements are taken.

Cold and warm. The same suite is run twice against one cache. The first run
populates it and the second must serve every prompt from it. This is the done
check and it verifies the mechanism, not the saving.

Cross configuration. The saving that matters is not a repeated run, because
Level 9 does not repeat runs. It runs sixteen configurations of the same four
epistemic switches over the same signals. The switches change what happens to
hypotheses after they are generated, so the first iteration of every situation
assembles a byte identical prompt in all sixteen and only later iterations
diverge. The third measurement runs all sixteen against one shared cache and
reports the rate actually achieved, which is what a Level 9 budget should be
built on.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.observability.llm_cache import CachingLLMFactory, ResponseCache  # noqa: E402
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.replay.offline import (  # noqa: E402
    MockLLM,
    OfflineReplay,
    synthetic_signals,
)
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "level6"
INERTIA_DISABLED = float("inf")


def run_suite(factory, signals, controls=None) -> None:
    """Drive one offline replay with the given factory and control set."""
    OfflineReplay(
        factory,
        controls=controls,
        seed=42,
        correlation=EntityCorrelation(),
    ).run(signals)


def main() -> int:
    """Measure cold, warm and cross configuration cache behaviour."""
    parser = argparse.ArgumentParser(description="Level 6 response cache measurement.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--signals", type=int, default=200)
    parser.add_argument("--devices", type=int, default=20)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    signals = synthetic_signals(args.signals, seed=args.seed, devices=args.devices)

    cold_path = RESULTS_DIR / "cache_repeat.json"
    if cold_path.exists():
        cold_path.unlink()

    model = MockLLM(seed=args.seed)

    cold_cache = ResponseCache(cold_path, model="mock")
    run_suite(CachingLLMFactory(lambda: model, cold_cache), signals)
    cold_cache.save()
    cold = cold_cache.stats.to_dict()
    calls_after_cold = model.calls

    warm_cache = ResponseCache(cold_path, model="mock")
    run_suite(CachingLLMFactory(lambda: model, warm_cache), signals)
    warm = warm_cache.stats.to_dict()
    calls_after_warm = model.calls

    shared_path = RESULTS_DIR / "cache_ablation.json"
    if shared_path.exists():
        shared_path.unlink()

    ablation_model = MockLLM(seed=args.seed)
    shared_cache = ResponseCache(shared_path, model="mock")
    shared_factory = CachingLLMFactory(lambda: ablation_model, shared_cache)

    per_configuration = []
    for unknown, sanity, decay, persistence in itertools.product(
        (True, False), repeat=4
    ):
        before = dict(shared_cache.stats.to_dict())
        run_suite(
            shared_factory,
            signals,
            controls=EpistemicControls(
                unknown_hypothesis_enabled=unknown,
                sanity_gate_enabled=sanity,
                asymmetric_decay_enabled=decay,
                persistence_required=persistence,
            ),
        )
        after = shared_cache.stats.to_dict()
        hits = after["hits"] - before["hits"]
        misses = after["misses"] - before["misses"]
        lookups = hits + misses
        per_configuration.append({
            "unknown_hypothesis_enabled": unknown,
            "sanity_gate_enabled": sanity,
            "asymmetric_decay_enabled": decay,
            "persistence_required": persistence,
            "lookups": lookups,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
        })
    shared_cache.save()

    report = {
        "seed": args.seed,
        "signals": args.signals,
        "devices": args.devices,
        "cold_run": cold,
        "warm_run": warm,
        "model_calls_during_cold_run": calls_after_cold,
        "model_calls_added_by_warm_run": calls_after_warm - calls_after_cold,
        "cross_configuration": {
            "configurations": len(per_configuration),
            "total_lookups": shared_cache.stats.lookups,
            "total_hits": shared_cache.stats.hits,
            "total_misses": shared_cache.stats.misses,
            "overall_hit_rate": round(shared_cache.stats.hit_rate, 4),
            "model_calls_without_cache": shared_cache.stats.lookups,
            "model_calls_with_cache": shared_cache.stats.misses,
            "calls_avoided": shared_cache.stats.hits,
            "per_configuration": per_configuration,
        },
    }

    (RESULTS_DIR / "cache_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    manifest = build_run_manifest(
        experiment="level6_cache",
        seed=args.seed,
        config={"signals": args.signals, "devices": args.devices},
        started_at=started,
        project_root=PROJECT_ROOT,
        extra={"overall_cross_configuration_hit_rate": report["cross_configuration"]["overall_hit_rate"]},
    )
    write_manifest(manifest, RESULTS_DIR / "manifest_cache.json")

    print("cold run  ", json.dumps(cold))
    print("warm run  ", json.dumps(warm))
    print("model calls during cold run     ", calls_after_cold)
    print("model calls added by warm run   ", calls_after_warm - calls_after_cold)
    print()
    cross = report["cross_configuration"]
    print(f"cross configuration over {cross['configurations']} ablation settings")
    print(f"  lookups              {cross['total_lookups']}")
    print(f"  hits                 {cross['total_hits']}")
    print(f"  misses               {cross['total_misses']}")
    print(f"  overall hit rate     {cross['overall_hit_rate']}")
    print(f"  model calls avoided  {cross['calls_avoided']}")
    print()
    print(f"{'U':>5} {'S':>5} {'A':>5} {'P':>5} {'lookups':>8} {'hits':>6} {'rate':>7}")
    for row in per_configuration:
        print(
            f"{str(row['unknown_hypothesis_enabled'])[0]:>5} "
            f"{str(row['sanity_gate_enabled'])[0]:>5} "
            f"{str(row['asymmetric_decay_enabled'])[0]:>5} "
            f"{str(row['persistence_required'])[0]:>5} "
            f"{row['lookups']:>8} {row['hits']:>6} {row['hit_rate']:>7}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
