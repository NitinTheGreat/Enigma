"""
Module: scripts/level9_cache_ablation.py

Measures the response cache hit rate per epistemic switch against a real model.

Why this is not the L6.8 measurement. L6.8 reported 0.936 across sixteen
configurations and stated plainly that the figure is an upper bound, because
it was taken with the deterministic mock whose three hypothesis descriptions
never vary. The prompt for a later iteration embeds the prior hypotheses being
refined, so under the mock that text is nearly constant across configurations
and the cache hits far more often than it can with a model whose text varies.
This script takes the same measurement with live Gemini, which is the only
version of it a Level 9 budget may rest on.

What is varied. The four single switch removals against the all on baseline,
rather than the full sixteen. A switch either changes the confidences a later
prompt prints or it does not, and the single removals isolate that per switch.
Running all sixteen measures the same four effects in combination at four
times the cost, which is not affordable at real model latency and is not
needed to budget.

The baseline runs first and populates the cache. Every later configuration
shares it, so its misses are exactly the prompts that configuration made
different, and its hits are exactly the calls the cache saved.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
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
from enigma_reason.observability.run_log import RunLogWriter  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402

from level7_validate import load_suite, stratified_sample  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "budget"
SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"

CONFIGURATIONS = (
    ("baseline", ""),
    ("minus_U", "U"),
    ("minus_S", "S"),
    ("minus_A", "A"),
    ("minus_P", "P"),
)


def controls_for(ablated: str) -> EpistemicControls:
    """Build the control set with the named switches removed."""
    return EpistemicControls(
        unknown_hypothesis_enabled="U" not in ablated,
        sanity_gate_enabled="S" not in ablated,
        asymmetric_decay_enabled="A" not in ablated,
        persistence_required="P" not in ablated,
    )


def main() -> int:
    """Run each configuration against one shared cache and report the deltas."""
    parser = argparse.ArgumentParser(description="Real model cache ablation.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--suite", type=str, default=str(SCENARIOS_DIR / "suite.jsonl"))
    parser.add_argument(
        "--cache",
        type=str,
        default=str(SCENARIOS_DIR / "gemini_cache_real.json"),
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)
    if args.limit:
        scenarios = stratified_sample(scenarios, args.limit)

    cache_path = Path(args.cache)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = ResponseCache(cache_path, model=settings.gemini_model)
    factory = CachingLLMFactory(_default_llm_factory, cache)
    entries_at_start = len(cache)

    log_path = RESULTS_DIR / f"cache_ablation_run_log_seed{args.seed}.jsonl"
    if log_path.exists():
        log_path.unlink()

    rows: list[dict[str, Any]] = []
    with RunLogWriter(log_path) as writer:
        for name, ablated in CONFIGURATIONS:
            before = dict(cache.stats.to_dict())
            began = time.monotonic()
            for scenario in scenarios:
                replay = OfflineReplay(
                    factory,
                    run_log=writer,
                    seed=args.seed,
                    correlation=EntityCorrelation(),
                    controls=controls_for(ablated),
                )
                replay.run(scenario.signals)
            elapsed = time.monotonic() - began
            after = cache.stats.to_dict()
            hits = after["hits"] - before["hits"]
            misses = after["misses"] - before["misses"]
            lookups = hits + misses
            rows.append(
                {
                    "seed": args.seed,
                    "configuration": name,
                    "ablated": ablated or "none",
                    "lookups": lookups,
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": round(hits / lookups, 4) if lookups else 0.0,
                    "elapsed_seconds": round(elapsed, 2),
                    "seconds_per_model_call": round(elapsed / misses, 3)
                    if misses
                    else 0.0,
                }
            )
            cache.save()
            print(
                f"{name:<10} ablated {ablated or 'none':<5} lookups {lookups:>5} "
                f"hits {hits:>5} misses {misses:>5} "
                f"hit rate {rows[-1]['hit_rate']:<7} {elapsed:.1f}s"
            )

    cache.save()
    non_baseline = [r for r in rows if r["configuration"] != "baseline"]
    pooled_lookups = sum(r["lookups"] for r in non_baseline)
    pooled_hits = sum(r["hits"] for r in non_baseline)

    report = {
        "seed": args.seed,
        "generated_at_utc": started.isoformat(),
        "model": settings.gemini_model,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "scenarios": len(scenarios),
        "cache_path": str(cache_path.relative_to(PROJECT_ROOT)),
        "cache_entries_at_start": entries_at_start,
        "cache_entries_at_end": len(cache),
        "configurations": rows,
        "pooled_hit_rate_excluding_baseline": round(pooled_hits / pooled_lookups, 4)
        if pooled_lookups
        else 0.0,
        "comparison": {
            "l6_8_mock_upper_bound": 0.936,
            "l6_8_first_iteration_floor": 0.31,
        },
        "reading": (
            "The pooled rate excludes the baseline because the baseline "
            "populates the cache and its own hit rate describes the run that "
            "filled it, not the reuse a further configuration obtains."
        ),
    }
    json_path = RESULTS_DIR / f"cache_ablation_real_seed{args.seed}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    csv_path = RESULTS_DIR / f"cache_ablation_real_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv_writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        csv_writer.writeheader()
        csv_writer.writerows(rows)

    print()
    print(
        f"pooled hit rate excluding baseline "
        f"{report['pooled_hit_rate_excluding_baseline']}"
    )
    print(f"cache entries {entries_at_start} to {len(cache)}")
    print(f"written {json_path.relative_to(PROJECT_ROOT)}")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
