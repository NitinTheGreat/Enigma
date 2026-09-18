"""
Module: scripts/probe_rate_limit.py

Establishes the hard constraint every Level 8 and Level 9 concurrency figure
depends on: the request rate the configured Gemini tier actually allows.

The tier is not reported by the API, so it is inferred from behaviour. A
burst of identical minimal prompts is fired at a chosen concurrency and the
outcome of each is recorded: latency, success, or the status the refusal
carried. A free tier key refuses with 429 once its requests per minute are
exhausted and carries a retry delay, and the quota metric named in the error
body distinguishes a per minute limit from a per day one.

Nothing here is inferred from documentation. The numbers written to
results/budget/rate_limit_seed{seed}.json are measured against the key in
Enigma-AIAgent/.env, and the quota strings the API returned are recorded
verbatim so the reading can be checked rather than trusted.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / "Enigma-AIAgent" / ".env")

sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.config import settings  # noqa: E402
from enigma_reason.graph.runner import _default_llm_factory  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results" / "budget"
PROMPT = "Reply with one word: acknowledged."


def fire(index: int) -> dict[str, Any]:
    """Issue one request and describe what came back."""
    started = time.monotonic()
    try:
        model = _default_llm_factory()
        reply = model.invoke(PROMPT)
        return {
            "index": index,
            "ok": True,
            "seconds": round(time.monotonic() - started, 3),
            "chars": len(str(reply.content)),
            "error": None,
            "quota": None,
            "retry_after": None,
        }
    except Exception as exc:
        text = str(exc)
        quota = re.findall(r"quota_metric[\"']?\s*[:=]\s*[\"']?([^\"',\n}]+)", text)
        retry = re.findall(r"retry_delay|retryDelay[^0-9]{0,20}(\d+)", text)
        return {
            "index": index,
            "ok": False,
            "seconds": round(time.monotonic() - started, 3),
            "chars": 0,
            "error": text[:600],
            "quota": quota or None,
            "retry_after": retry[0] if retry else None,
        }


def main() -> int:
    """Measure the achievable request rate and record the refusals verbatim."""
    parser = argparse.ArgumentParser(description="Gemini rate limit probe.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--requests", type=int, default=12)
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    wall = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        records = list(pool.map(fire, range(args.requests)))

    elapsed = time.monotonic() - wall
    ok = [r for r in records if r["ok"]]
    failed = [r for r in records if not r["ok"]]
    latencies = sorted(r["seconds"] for r in ok)

    report = {
        "seed": args.seed,
        "started_at": started.isoformat(),
        "model": settings.gemini_model,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "succeeded": len(ok),
        "refused": len(failed),
        "achieved_requests_per_minute": round(len(ok) / elapsed * 60, 1) if elapsed else 0,
        "latency_seconds": {
            "min": latencies[0] if latencies else None,
            "median": latencies[len(latencies) // 2] if latencies else None,
            "max": latencies[-1] if latencies else None,
            "mean": round(sum(latencies) / len(latencies), 3) if latencies else None,
        },
        "quota_metrics_returned": sorted(
            {q for r in failed if r["quota"] for q in r["quota"]}
        ),
        "first_refusal": failed[0]["error"] if failed else None,
        "records": records,
    }

    out = RESULTS_DIR / f"rate_limit_seed{args.seed}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"model {settings.gemini_model}  seed {args.seed}")
    print(
        f"requests {args.requests} at concurrency {args.concurrency}  "
        f"elapsed {elapsed:.1f}s"
    )
    print(f"succeeded {len(ok)}  refused {len(failed)}")
    print(f"achieved requests per minute {report['achieved_requests_per_minute']}")
    print(f"latency seconds {json.dumps(report['latency_seconds'])}")
    if report["quota_metrics_returned"]:
        print(f"quota metrics returned {report['quota_metrics_returned']}")
    if failed:
        print()
        print("first refusal verbatim:")
        print(failed[0]["error"])
    print()
    print(f"written {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
