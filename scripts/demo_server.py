"""
Demo server for the Enigma review dashboard.

Streams real-time ML model output and Gemini AI reasoning through
a WebSocket so the HTML frontend can visualise both layers live.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load .env BEFORE enigma imports
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "Enigma-AIAgent" / ".env")

sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from enigma_reason.config import settings
from enigma_reason.core.reasoning_engine import ReasoningEngine
from enigma_reason.domain.signal import Signal
from enigma_reason.explain.builder import build_explanation
from enigma_reason.explain.formatter import ExplanationFormatter
from enigma_reason.graph.runner import _default_llm_factory, run_reasoning
from enigma_reason.replay.offline import synthetic_signals
from enigma_reason.store.correlation import EntityCorrelation
from enigma_reason.store.situation_store import SituationStore

logging.basicConfig(level="INFO", format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("demo_server")

# ── State ────────────────────────────────────────────────────────────────────

engine = ReasoningEngine()
store = SituationStore(
    correlation=EntityCorrelation(),
    reasoning_engine=engine,
    clock_mode=settings.clock_mode,
)

app = FastAPI(title="Enigma Demo Dashboard Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

dashboard_clients: set[WebSocket] = set()

# ── Prompt/Response interceptor ──────────────────────────────────────────────

_last_prompt = ""
_last_response = ""
_last_parsed: list[dict] = []
_llm_call_count = 0
_llm_fallback_count = 0


class InterceptingLLM:
    """Wraps the real Gemini model to capture prompts and responses."""
    def __init__(self, inner):
        self._inner = inner
    def invoke(self, prompt: str):
        global _last_prompt, _last_response, _last_parsed, _llm_call_count
        _last_prompt = prompt
        _llm_call_count += 1
        response = self._inner.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        _last_response = text
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()
            _last_parsed = json.loads(cleaned)
        except Exception:
            _last_parsed = []
        return response


def intercepting_factory():
    global _llm_fallback_count
    try:
        inner = _default_llm_factory()
        return InterceptingLLM(inner)
    except Exception:
        _llm_fallback_count += 1
        raise


# ── Broadcast ────────────────────────────────────────────────────────────────

async def broadcast(message: dict):
    text = json.dumps(message, default=str)
    dead = set()
    for ws in dashboard_clients:
        try:
            await ws.send_text(text)
        except Exception:
            dead.add(ws)
    dashboard_clients.difference_update(dead)


# ── Signal replay task ───────────────────────────────────────────────────────

replay_running = False
replay_stats = {"signals_ingested": 0, "situations_created": 0, "analyses_run": 0, "analyses_failed": 0, "total_signals": 0, "wall_clock": 0.0}


async def run_replay(signal_count: int = 60, devices: int = 6, delay: float = 1.5):
    global replay_running
    replay_running = True
    for k in replay_stats:
        replay_stats[k] = 0
    replay_stats["total_signals"] = signal_count

    signals = synthetic_signals(signal_count, seed=42, devices=devices)
    replay_stats["total_signals"] = len(signals)

    await broadcast({"type": "replay_started", "total_signals": len(signals), "devices": devices, "model": settings.gemini_model, "timestamp": datetime.now(timezone.utc).isoformat()})

    start_time = time.perf_counter()

    for idx, signal in enumerate(signals):
        if not replay_running:
            break

        # Step 1: Ingest signal via async store API
        situation = await store.ingest(signal)
        replay_stats["signals_ingested"] += 1
        sit_count = await store.active_count()
        replay_stats["situations_created"] = sit_count

        await broadcast({
            "type": "signal_ingested", "index": idx + 1, "total": len(signals),
            "signal": {
                "signal_id": str(signal.signal_id),
                "signal_type": signal.signal_type.value if signal.signal_type else "unknown",
                "entity": str(signal.entity.identifier) if signal.entity else None,
                "anomaly_score": round(signal.anomaly_score, 4),
                "confidence": round(signal.confidence, 4),
                "source": signal.source,
                "abstained": signal.abstained,
            },
            "situation": {
                "situation_id": str(situation.situation_id),
                "evidence_count": situation.evidence_count,
            },
            "stats": dict(replay_stats),
        })

        # Step 2: Run analysis every 3rd signal (to avoid rate limiting)
        if (idx + 1) % 3 == 0:
            try:
                temporal = situation.temporal_snapshot()
                reasoning = engine.evaluate(situation)
                context = {
                    "evidence_count": reasoning.evidence_count,
                    "event_rate_per_minute": round(temporal.event_rate_per_minute, 4),
                    "active_duration_seconds": round(temporal.active_duration_seconds, 2),
                    "burst_detected": reasoning.burst_detected,
                    "quiet_detected": reasoning.quiet_detected,
                    "trend": reasoning.trend.value,
                    "confidence_level": round(reasoning.confidence_level, 4),
                    "source_diversity": reasoning.source_diversity,
                    "mean_anomaly_score": round(reasoning.mean_anomaly_score, 4),
                }

                await broadcast({
                    "type": "analysis_started",
                    "situation_id": str(situation.situation_id),
                    "context": context,
                    "reasoning": context,
                })

                t0 = time.perf_counter()
                final_state = await asyncio.to_thread(
                    partial(run_reasoning, situation, temporal, reasoning, llm_factory=intercepting_factory)
                )
                reasoning_time = time.perf_counter() - t0

                explanation = build_explanation(final_state, reasoning, temporal)
                human_text = ExplanationFormatter.format_plain(explanation)
                replay_stats["analyses_run"] += 1

                await broadcast({
                    "type": "analysis_complete",
                    "situation_id": str(situation.situation_id),
                    "reasoning_time_seconds": round(reasoning_time, 3),
                    "gemini": {
                        "prompt_preview": _last_prompt[:800] if _last_prompt else "(no prompt)",
                        "prompt_length": len(_last_prompt),
                        "raw_response": _last_response[:1200] if _last_response else "(no response)",
                        "response_length": len(_last_response),
                        "parsed_hypotheses": _last_parsed if _last_parsed else [],
                        "used_fallback": len(_last_parsed) == 0,
                        "total_calls": _llm_call_count,
                        "total_fallbacks": _llm_fallback_count,
                    },
                    "langgraph": {
                        "hypotheses": [
                            {"id": h.get("hypothesis_id", "?")[:8], "description": h.get("description", "?"),
                             "confidence": round(h.get("confidence", 0), 4), "status": h.get("status", "?"),
                             "velocity": round(h.get("belief_velocity", 0), 4), "dominant_iters": h.get("dominant_iterations", 0)}
                            for h in final_state.get("hypotheses", [])
                        ],
                        "convergence_score": round(final_state.get("convergence_score", 0), 4),
                        "iterations": final_state.get("iteration_count", 0),
                        "stability": round(final_state.get("belief_stability_score", 0), 4),
                    },
                    "explanation": {
                        "undecided": explanation.undecided,
                        "dominant_description": explanation.dominant_hypothesis_description,
                        "dominant_confidence": explanation.dominant_confidence,
                        "human_readable": human_text,
                        "sections": [{"type": s.section_type.value, "title": s.title, "bullets": s.bullet_points} for s in explanation.explanation_sections],
                    },
                    "stats": dict(replay_stats),
                })
            except Exception as exc:
                replay_stats["analyses_failed"] += 1
                logger.error("Analysis failed: %s", exc, exc_info=True)
                await broadcast({"type": "analysis_error", "situation_id": str(situation.situation_id), "error": str(exc)})

        await asyncio.sleep(delay)

    replay_stats["wall_clock"] = round(time.perf_counter() - start_time, 2)
    replay_running = False
    await broadcast({"type": "replay_complete", "stats": dict(replay_stats)})


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_dashboard():
    return FileResponse(PROJECT_ROOT / "scripts" / "demo_dashboard.html")

@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.gemini_model, "api_key_set": bool(os.environ.get("GOOGLE_API_KEY")), "replay_running": replay_running}

@app.websocket("/ws/demo")
async def demo_ws(websocket: WebSocket):
    global replay_running
    await websocket.accept()
    dashboard_clients.add(websocket)
    logger.info("Dashboard client connected (%d total)", len(dashboard_clients))
    await websocket.send_text(json.dumps({"type": "connected", "model": settings.gemini_model, "api_key_set": bool(os.environ.get("GOOGLE_API_KEY")), "timestamp": datetime.now(timezone.utc).isoformat()}))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            cmd = msg.get("command")
            if cmd == "start_replay":
                asyncio.create_task(run_replay(msg.get("signal_count", 60), msg.get("devices", 6), msg.get("delay", 1.5)))
                await websocket.send_text(json.dumps({"type": "ack", "command": "start_replay"}))
            elif cmd == "stop_replay":
                replay_running = False
                await websocket.send_text(json.dumps({"type": "ack", "command": "stop_replay"}))
            elif cmd == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        dashboard_clients.discard(websocket)
        logger.info("Dashboard client disconnected")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("  ENIGMA DEMO DASHBOARD SERVER")
    print(f"  Model: {settings.gemini_model}")
    print(f"  API Key: {'SET' if os.environ.get('GOOGLE_API_KEY') else 'MISSING'}")
    print(f"  Open: http://localhost:8765")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
