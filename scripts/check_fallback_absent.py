"""
Module: scripts/check_fallback_absent.py

Proves a run log came from a model rather than from the fallback strings.

The run log stores a twelve character hash of each hypothesis description,
not the description itself, so whether a run actually reached Gemini cannot be
read off the log by eye. Hashing the three fixed strings at nodes.py:200-202
and searching for them settles it: their presence means generation raised and
was substituted on at least one iteration, and their absence across every
iteration means every hypothesis in the log came from the model.

This is the check appendix L7.8 rests on. Without it a real run and an
unconfigured one are indistinguishable in the artefact they leave behind.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.graph.nodes import _fallback_hypotheses  # noqa: E402
from enigma_reason.observability.run_log import text_hash  # noqa: E402


def main() -> int:
    """Report whether any fallback hypothesis appears in the run log."""
    parser = argparse.ArgumentParser(description="Fallback absence check.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log", type=str, required=True)
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = (PROJECT_ROOT / log_path).resolve()

    fallback = {}
    for entry in _fallback_hypotheses():
        description = entry["description"]
        fallback[text_hash(description)] = description

    seen: Counter[str] = Counter()
    unknown_hash = None
    iterations = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        iterations += 1
        for hypothesis in json.loads(line).get("hypotheses", []):
            digest = str(hypothesis.get("text_hash", ""))
            seen[digest] += 1
            if hypothesis.get("is_unknown"):
                unknown_hash = digest

    present = {h: seen[h] for h in fallback if seen.get(h)}
    distinct = len([h for h in seen if h != unknown_hash])

    print(f"seed {args.seed}")
    print(f"log {log_path.relative_to(PROJECT_ROOT)}")
    print(f"iterations {iterations}   distinct hypothesis hashes {distinct}")
    print()
    for digest, description in fallback.items():
        mark = "PRESENT" if digest in present else "absent"
        print(f"  {mark:<8} {digest}  {description}")
    print()
    if present:
        print("VERDICT the fallback path was taken on at least one iteration")
        return 1
    print("VERDICT no fallback hypothesis appears, every hypothesis came from the model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
