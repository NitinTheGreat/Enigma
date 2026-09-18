"""
Module: scripts/level6_load.py

Measures analysis backlog against arrival rate.

Section C4 of paper/EVIDENCE.md records four structural problems, of which the
first three are about the same thing: work arrives faster than it is served and
nothing anywhere reports that this is happening. This script makes the backlog
a number.

The arrival side is real. Signals cross the real correlation strategy, the real
store and the real bounded pool, and the dashboard broadcast is the real code
path writing to a stub client.

The service side is simulated. Each analysis sleeps for a fixed service time
rather than calling Gemini, for two reasons. Driving sixteen records per second
against a live model would cost money to establish a result that is a property
of the queue and not of the model, and a variable service time would make the
saturation point irreproducible. The service time is a parameter and is written
into the output, so the reported saturation point is stated relative to a
service time rather than presented as unconditional.

Little's law gives the prediction this checks: a system serving at
max_concurrent / service_seconds analyses per second is stable below that rate
and unbounded above it. With the defaults of four concurrent and six seconds,
service capacity is 0.67 analyses per second, so all three tested rates are
above it and the question is only how the system fails.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.core.reasoning_engine import ReasoningEngine  # noqa: E402
from enigma_reason.observability.backpressure import AnalysisPool  # noqa: E402
from enigma_reason.observability.latency import LatencyRecorder, Stage  # noqa: E402
from enigma_reason.observability.manifest import build_run_manifest, write_manifest  # noqa: E402
from enigma_reason.replay.offline import synthetic_signals  # noqa: E402
from enigma_reason.store.situation_store import SituationStore  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "level6"


class StubClient:
    """Stands in for a dashboard websocket, counting what it receives."""

    def __init__(self) -> None:
        self.received = 0
        self.bytes_received = 0

    async def send_text(self, message: str) -> None:
        """Accept one broadcast."""
        self.received += 1
        self.bytes_received += len(message)


class SimulatedAnalyser:
    """Runs the real broadcast path with a fixed cost standing in for Gemini."""

    def __init__(
        self,
        service_seconds: float,
        latency: LatencyRecorder,
        client: StubClient,
    ) -> None:
        self.service_seconds = service_seconds
        self.latency = latency
        self.client = client
        self.analyses = 0

    async def analyse(self, situation) -> None:
        """Spend the service time, then broadcast the real payload shape."""
        engine = ReasoningEngine()
        with self.latency.measure(Stage.DETERMINISTIC):
            temporal = situation.temporal_snapshot()
            reasoning = engine.evaluate(situation)

        with self.latency.measure(Stage.LANGGRAPH):
            await asyncio.sleep(self.service_seconds)

        with self.latency.measure(Stage.EXPLANATION):
            payload = {
                "type": "situation_analysis",
                "situation": situation.summary(),
                "temporal": temporal.model_dump(),
                "reasoning": reasoning.model_dump(),
            }

        with self.latency.measure(Stage.BROADCAST):
            await self.client.send_text(json.dumps(payload, default=str))

        self.analyses += 1


async def run_rate(
    rate: float,
    *,
    seed: int,
    duration: float,
    service_seconds: float,
    max_concurrent: int,
    max_pending: int,
    devices: int,
) -> dict:
    """Drive one arrival rate and return what the backlog did."""
    latency = LatencyRecorder()
    client = StubClient()
    analyser = SimulatedAnalyser(service_seconds, latency, client)
    pool = AnalysisPool(
        max_concurrent=max_concurrent,
        max_pending=max_pending,
        latency_recorder=latency,
    )
    store = SituationStore(clock_mode="separated")

    planned = max(1, int(rate * duration))
    signals = synthetic_signals(planned, seed=seed, devices=devices)
    interval = 1.0 / rate

    samples: list[int] = []
    loop = asyncio.get_running_loop()
    started = loop.time()

    for index, signal in enumerate(signals):
        with latency.measure(Stage.INGEST):
            with latency.measure(Stage.ATTACH):
                situation = store._find_or_create(signal)
                situation.attach_evidence(signal)

        pool.submit(lambda s=situation: analyser.analyse(s))
        samples.append(pool.pending + pool.running)

        target = started + interval * (index + 1)
        delay = target - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)

    offered_seconds = loop.time() - started
    backlog_at_stop = pool.pending + pool.running
    drained = await pool.drain(timeout=service_seconds * max_pending + 60)
    total_seconds = loop.time() - started

    snapshot = pool.snapshot()
    service_capacity = max_concurrent / service_seconds

    return {
        "arrival_rate_per_second": rate,
        "offered_signals": len(signals),
        "offered_seconds": round(offered_seconds, 3),
        "achieved_arrival_rate": round(len(signals) / offered_seconds, 3),
        "service_capacity_per_second": round(service_capacity, 3),
        "oversubscription_factor": round(rate / service_capacity, 2),
        "backlog_when_arrivals_stopped": backlog_at_stop,
        "peak_backlog": snapshot.peak_pending + snapshot.peak_running,
        "peak_pending": snapshot.peak_pending,
        "peak_running": snapshot.peak_running,
        "mean_backlog_during_arrivals": round(sum(samples) / len(samples), 2),
        "submitted": snapshot.submitted,
        "admitted": snapshot.submitted - snapshot.shed,
        "shed": snapshot.shed,
        "shed_fraction": round(snapshot.shed / snapshot.submitted, 4),
        "completed": snapshot.completed,
        "failed": snapshot.failed,
        "broadcasts_delivered": client.received,
        "saturated": snapshot.shed > 0,
        "drained_within_timeout": drained,
        "total_seconds_including_drain": round(total_seconds, 3),
        "drain_seconds": round(total_seconds - offered_seconds, 3),
        "admission_wait_ms": latency.summary().get("analysis_admission_wait", {}),
        "latency_ms": latency.summary(),
    }


async def main_async(args) -> int:
    """Run every configured rate and write the comparison."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    rows = []
    for rate in args.rates:
        print(f"running arrival rate {rate} records/s ...", flush=True)
        row = await run_rate(
            rate,
            seed=args.seed,
            duration=args.duration,
            service_seconds=args.service_seconds,
            max_concurrent=args.max_concurrent,
            max_pending=args.max_pending,
            devices=args.devices,
        )
        row["seed"] = args.seed
        rows.append(row)

    output = RESULTS_DIR / "queue_depth.jsonl"
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    manifest = build_run_manifest(
        experiment="level6_queue_depth",
        seed=args.seed,
        config={
            "rates": args.rates,
            "duration_seconds": args.duration,
            "service_seconds": args.service_seconds,
            "max_concurrent": args.max_concurrent,
            "max_pending": args.max_pending,
            "devices": args.devices,
        },
        started_at=started,
        project_root=PROJECT_ROOT,
        extra={"service_time_is_simulated": True},
    )
    write_manifest(manifest, RESULTS_DIR / "manifest_queue_depth.json")

    print()
    header = (
        f"{'rate/s':>7} {'offered':>8} {'peak':>6} {'mean':>7} {'shed':>6} "
        f"{'shed%':>7} {'done':>6} {'drain s':>8} {'saturated':>10}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['arrival_rate_per_second']:>7} {row['offered_signals']:>8} "
            f"{row['peak_backlog']:>6} {row['mean_backlog_during_arrivals']:>7} "
            f"{row['shed']:>6} {row['shed_fraction'] * 100:>6.1f}% "
            f"{row['completed']:>6} {row['drain_seconds']:>8.1f} "
            f"{str(row['saturated']):>10}"
        )
    print()
    print(f"service capacity {rows[0]['service_capacity_per_second']} analyses/s "
          f"from {args.max_concurrent} concurrent at {args.service_seconds}s each")
    print(f"written to {output}")
    return 0


def main() -> int:
    """Parse arguments and run the load sweep."""
    parser = argparse.ArgumentParser(description="Level 6 queue depth under load.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rates", type=float, nargs="+", default=[1.0, 4.0, 16.0])
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--service-seconds", type=float, default=6.0)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--max-pending", type=int, default=64)
    parser.add_argument("--devices", type=int, default=16)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
