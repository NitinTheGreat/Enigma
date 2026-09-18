"""
Module: scripts/probe_dashboard_ws.py

Measures how long the dashboard websocket takes to deliver an analysis push.

The dashboard only receives a situation when the reasoning layer finishes
analysing it, and that analysis runs per arriving signal in an unbounded task
fan out. If the backlog grows, pushes arrive minutes apart and the interface
looks broken while the socket is perfectly healthy.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time


async def probe(uri: str, seconds: float) -> None:
    """Connect and report every push received within the window."""
    import websockets

    started = time.perf_counter()
    received = 0
    first_at = None

    print(f"connecting to {uri}")
    async with websockets.connect(uri) as socket:
        print(f"connected after {time.perf_counter() - started:.2f}s, listening for {seconds:.0f}s")
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            remaining = deadline - time.perf_counter()
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            if raw == "pong":
                continue
            received += 1
            elapsed = time.perf_counter() - started
            if first_at is None:
                first_at = elapsed
            payload = json.loads(raw)
            situation = payload.get("situation", {})
            print(
                f"  push {received:>3} at {elapsed:>6.2f}s  "
                f"situation {situation.get('situation_id', '')[:8]}  "
                f"evidence {situation.get('evidence_count')}  "
                f"version {situation.get('version')}"
            )

    total = time.perf_counter() - started
    print()
    print(f"pushes received      : {received}")
    print(f"first push at        : {first_at if first_at is None else round(first_at, 2)}s")
    print(f"observed push rate   : {received / total * 60:.1f} per minute")


def main() -> None:
    """Parse arguments and run the probe."""
    parser = argparse.ArgumentParser(description="Probe the dashboard websocket push rate.")
    parser.add_argument("--uri", type=str, default="ws://127.0.0.1:8000/ws/dashboard")
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    asyncio.run(probe(args.uri, args.seconds))


if __name__ == "__main__":
    main()
