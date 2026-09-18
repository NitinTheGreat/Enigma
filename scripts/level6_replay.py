"""
Module: scripts/level6_replay.py

Drives the offline reasoning stack and writes the Level 6 evidence.

Produces, under results/level6:
    run_log_<tag>.jsonl      one record per reasoning iteration
    latency_<tag>.json       per stage percentiles
    manifest_<tag>.json      provenance for the run
    summary_<tag>.json       counts and wall clock

The mocked model is the default because the run logger, the latency
percentiles and the cache mechanics are all testable without spending money on
Gemini. Pass --llm real to drive the actual model.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.foundation.clock import ClockMode  # noqa: E402
from enigma_reason.graph.runner import _default_llm_factory  # noqa: E402
from enigma_reason.observability.llm_cache import CachingLLMFactory, ResponseCache  # noqa: E402
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.observability.run_log import RunLogWriter  # noqa: E402
from enigma_reason.replay.offline import (  # noqa: E402
    OfflineReplay,
    load_signals,
    mock_llm_factory,
    synthetic_signals,
)
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "level6"
DEFAULT_SIGNALS = PROJECT_ROOT / "results" / "baselines" / "replay_signals.jsonl"


def build_factory(mode: str, cache_path: Path | None, model_name: str):
    """Return the model factory and the cache backing it, if any."""
    inner = mock_llm_factory(seed=42) if mode == "mock" else _default_llm_factory
    if cache_path is None:
        return inner, None
    cache = ResponseCache(cache_path, model=model_name)
    return CachingLLMFactory(inner, cache), cache


def main() -> int:
    """Run one offline replay and write its evidence."""
    parser = argparse.ArgumentParser(description="Level 6 offline reasoning replay.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tag", type=str, default="mock")
    parser.add_argument("--signals", type=int, default=400)
    parser.add_argument("--devices", type=int, default=16)
    parser.add_argument("--analyse-every", type=int, default=1)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--llm", choices=("mock", "real"), default="mock")
    parser.add_argument("--clock-mode", type=str, default=ClockMode.SEPARATED.value)
    parser.add_argument("--cache", type=str, default="")
    parser.add_argument(
        "--correlation",
        choices=("default", "entity"),
        default="default",
        help=(
            "default groups by signal type and entity, entity groups by entity "
            "alone and so yields one situation per device, which is what the "
            "live server uses."
        ),
    )
    parser.add_argument(
        "--signals-file",
        type=str,
        default="",
        help="JSONL of exported sensor signals. Synthetic signals when omitted.",
    )
    parser.add_argument(
        "--model-artefact",
        type=str,
        default="",
        help=(
            "Directory or file holding the sensor checkpoint whose outputs fed "
            "this run. Hashed into the manifest so a result names the model "
            "that produced its inputs."
        ),
    )
    args = parser.parse_args()

    random.seed(args.seed)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    if args.signals_file:
        source = Path(args.signals_file)
        signals = load_signals(source, limit=args.signals)
        dataset = source
    elif DEFAULT_SIGNALS.is_file() and args.llm == "real":
        signals = load_signals(DEFAULT_SIGNALS, limit=args.signals)
        dataset = DEFAULT_SIGNALS
    else:
        signals = synthetic_signals(args.signals, seed=args.seed, devices=args.devices)
        dataset = None

    cache_path = Path(args.cache) if args.cache else None
    model_name = "mock" if args.llm == "mock" else "gemini"
    factory, cache = build_factory(args.llm, cache_path, model_name)

    run_log_path = RESULTS_DIR / f"run_log_{args.tag}.jsonl"
    if run_log_path.exists():
        run_log_path.unlink()

    with RunLogWriter(run_log_path) as writer:
        replay = OfflineReplay(
            factory,
            run_log=writer,
            clock_mode=args.clock_mode,
            seed=args.seed,
            analyse_every=args.analyse_every,
            max_iterations=args.max_iterations,
            correlation=EntityCorrelation() if args.correlation == "entity" else None,
        )
        result = replay.run(signals)
        writer.flush()
        result.iterations_logged = writer.written
        log_dropped = writer.dropped

    if cache is not None:
        cache.save()
        result.cache = cache.stats.to_dict()

    summary = result.to_dict()
    summary["seed"] = args.seed
    summary["tag"] = args.tag
    summary["llm"] = args.llm
    summary["clock_mode"] = args.clock_mode
    summary["run_log_dropped"] = log_dropped
    summary["run_log_path"] = str(run_log_path)
    summary["correlation"] = args.correlation

    (RESULTS_DIR / f"summary_{args.tag}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (RESULTS_DIR / f"latency_{args.tag}.json").write_text(
        json.dumps({"seed": args.seed, "stages": result.latency}, indent=2),
        encoding="utf-8",
    )

    manifest = build_run_manifest(
        experiment=f"level6_replay_{args.tag}",
        seed=args.seed,
        config={
            "signals": args.signals,
            "devices": args.devices,
            "analyse_every": args.analyse_every,
            "max_iterations": args.max_iterations,
            "llm": args.llm,
            "clock_mode": args.clock_mode,
            "cache": str(cache_path) if cache_path else None,
        },
        started_at=started,
        project_root=PROJECT_ROOT,
        dataset=dataset,
        model_artefact=Path(args.model_artefact) if args.model_artefact else None,
        extra={
            "analyses_run": result.analyses_run,
            "iterations_logged": result.iterations_logged,
            "run_log_dropped": log_dropped,
            "cache": result.cache,
        },
    )
    write_manifest(manifest, RESULTS_DIR / f"manifest_{args.tag}.json")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
