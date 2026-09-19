"""
Module: scripts/level7_label_extract.py

Extracts the hypothesis texts of the real model run so they can be labelled.

The run log stores a twelve character hash of each hypothesis, not its text,
so the texts have to be recovered from the response cache written by the same
run. Each cached value is the model's raw JSON array of hypotheses; hashing
each description with the same function the run logger used rebuilds the
hash to text map the run itself never persisted.

What is sampled. Distinct non UNKNOWN hypothesis texts that actually appear
in the run log, sampled deterministically from a seeded generator, stratified
across situations so no single scenario dominates the labelled set. The
scenario each text was produced under is carried with it, because a label is
only meaningful against the ground truth the hypothesis was answering.

The labelling task these feed is not whether a hypothesis matched its own
scenario. It is which of the six narrative categories the text describes, if
any. That is a harder and more useful question: it exercises all six
categories rather than the two the four scenario slice happens to cover, and
it is exactly the discrimination the embedding scorer has to perform.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))

from enigma_reason.observability.run_log import text_hash  # noqa: E402
from scenarios.generator import CATEGORIES  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
RESULTS_DIR = PROJECT_ROOT / "results" / "scoring"


def texts_from_cache(path: Path) -> dict[str, str]:
    """Rebuild the hash to text map from the run's response cache."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for raw in payload.get("entries", {}).values():
        try:
            hypotheses = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(hypotheses, list):
            continue
        for entry in hypotheses:
            if not isinstance(entry, dict):
                continue
            description = str(entry.get("description", "")).strip()
            if description:
                mapping[text_hash(description)] = description
    return mapping


def main() -> int:
    """Write the candidate set for hand labelling."""
    parser = argparse.ArgumentParser(description="Extract hypotheses to label.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument(
        "--log", type=str, default=str(SCENARIOS_DIR / "validation_run_log_real.jsonl")
    )
    parser.add_argument(
        "--cache", type=str, default=str(SCENARIOS_DIR / "gemini_cache_real.json")
    )
    parser.add_argument(
        "--outcomes",
        type=str,
        default=str(SCENARIOS_DIR / "validation_outcomes_real.jsonl"),
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    mapping = texts_from_cache(Path(args.cache))

    scenario_of: dict[str, dict[str, Any]] = {}
    for line in Path(args.outcomes).read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        scenario_of[row["situation_id"]] = {
            "scenario_id": row["scenario_id"],
            "regime": row["regime"],
            "expected_conclusion": row["expected_conclusion"],
        }

    by_situation: dict[str, dict[str, str]] = defaultdict(dict)
    unresolved = 0
    for line in Path(args.log).read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        record = json.loads(line)
        situation = str(record.get("situation_id"))
        for hypothesis in record.get("hypotheses", []):
            if hypothesis.get("is_unknown"):
                continue
            digest = str(hypothesis.get("text_hash"))
            text = mapping.get(digest)
            if text is None:
                unresolved += 1
                continue
            by_situation[situation][digest] = text

    rng = random.Random(args.seed)
    situations = sorted(by_situation)
    pooled: list[dict[str, Any]] = []
    for situation in situations:
        items = sorted(by_situation[situation].items())
        rng.shuffle(items)
        meta = scenario_of.get(situation, {})
        for digest, text in items:
            pooled.append(
                {
                    "text_hash": digest,
                    "text": text,
                    "situation_id": situation,
                    "scenario_id": meta.get("scenario_id"),
                    "regime": meta.get("regime"),
                    "expected_conclusion": meta.get("expected_conclusion"),
                }
            )

    per_situation = max(1, args.count // max(len(situations), 1))
    chosen: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    for situation in situations:
        taken = 0
        for item in pooled:
            if item["situation_id"] != situation:
                continue
            if item["text"] in seen_text:
                continue
            chosen.append(item)
            seen_text.add(item["text"])
            taken += 1
            if taken >= per_situation:
                break
    for item in pooled:
        if len(chosen) >= args.count:
            break
        if item["text"] in seen_text:
            continue
        chosen.append(item)
        seen_text.add(item["text"])
    chosen = chosen[: args.count]

    out = RESULTS_DIR / f"label_candidates_seed{args.seed}.jsonl"
    with out.open("w", encoding="utf-8") as handle:
        for index, item in enumerate(chosen):
            item["candidate_index"] = index
            handle.write(json.dumps(item, separators=(",", ":")) + "\n")

    print(f"seed {args.seed}")
    print(f"cache texts recovered      {len(mapping)}")
    print(f"unresolved hypothesis rows {unresolved}")
    print(f"situations                 {len(situations)}")
    print(f"distinct texts in log      {len(seen_text)}")
    print(f"candidates written         {len(chosen)}")
    print(f"categories available       {[c.name for c in CATEGORIES]}")
    print(f"written {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
