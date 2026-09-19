"""
Module: scripts/level7_hand_labels.py

Carries the hand labels for the fifty extracted hypotheses and writes them
joined to their candidates.

The labelling question. For each hypothesis text, which of the six narrative
categories does it describe, if any. This is asked of the text alone, without
reference to the scenario it came from, so that a label records what the text
says rather than what the scenario wanted it to say.

The rule applied. A category is assigned only when the text describes that
category's defining action. Reconnaissance is scanning, probing, enumeration
or discovery. Lateral movement is moving or spreading between internal
systems, not merely being present on several of them. Data exfiltration is
data leaving the estate, not internal transfer. Text describing benign
activity, misconfiguration, or a generic compromise with no narrative is
labelled none. Generic attacker activity that names no narrative in the six,
such as an unspecified exploit attempt, is also none.

Provenance and its limits. These are the judgements of one annotator, the
assistant that produced this file, recorded before the embedding scorer was
run so that the labels could not be fitted to its output. There is no second
annotator and therefore no inter annotator agreement figure. Where a text was
genuinely arguable the reasoning is recorded against it rather than hidden,
so a reader can disagree with a specific call.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results" / "scoring"

NONE = "none"
RECON = "reconnaissance_sweep"

LABELS: dict[int, str] = {
    0: NONE, 1: RECON, 2: NONE, 3: RECON, 4: NONE,
    5: NONE, 6: RECON, 7: NONE, 8: RECON, 9: RECON,
    10: NONE, 11: RECON, 12: RECON, 13: NONE, 14: NONE,
    15: NONE, 16: RECON, 17: NONE, 18: NONE, 19: RECON,
    20: NONE, 21: RECON, 22: NONE, 23: RECON, 24: NONE,
    25: NONE, 26: RECON, 27: NONE, 28: NONE, 29: NONE,
    30: RECON, 31: NONE, 32: RECON, 33: NONE, 34: NONE,
    35: NONE, 36: RECON, 37: NONE, 38: NONE, 39: NONE,
    40: RECON, 41: NONE, 42: NONE, 43: NONE, 44: NONE,
    45: NONE, 46: NONE, 47: NONE, 48: NONE, 49: NONE,
}

RATIONALE: dict[int, str] = {
    5: "compromise present on several hosts is a state, not movement between "
       "them, so not lateral movement under the defining action rule",
    13: "malicious but names no narrative among the six",
    24: "possible malware names no narrative among the six",
    26: "enumeration is the defining action and enumeration is reconnaissance, "
        "even though the actor is internal and already compromised",
    30: "a stealthy probe is probing",
    35: "an unspecified exploit attempt is not one of the six narratives",
    40: "scanning is the defining action, the exploit clause adds nothing",
    41: "generic attack activity naming no narrative among the six",
    44: "attacks targeting services is not service denial, which requires "
        "flooding, saturation or exhaustion of availability",
    47: "internal data transfer is not exfiltration, which requires data "
        "leaving the estate. The keyword scorer matches 'data transfer' here "
        "and would call this data exfiltration, which is a false positive",
}


def main() -> int:
    """Join the labels to their candidates and write the labelled set."""
    parser = argparse.ArgumentParser(description="Hand labels for the scorer study.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    candidates_path = RESULTS_DIR / f"label_candidates_seed{args.seed}.jsonl"
    candidates = [
        json.loads(line)
        for line in candidates_path.read_text(encoding="utf-8").splitlines()
        if line
    ]

    missing = [c["candidate_index"] for c in candidates if c["candidate_index"] not in LABELS]
    if missing:
        print(f"no label recorded for candidate indices {missing}")
        return 1

    out_path = RESULTS_DIR / f"hand_labels_seed{args.seed}.jsonl"
    with out_path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            index = candidate["candidate_index"]
            row = dict(candidate)
            row["label"] = LABELS[index]
            row["label_is_match"] = LABELS[index] != NONE
            row["annotator"] = "assistant, single annotator, labelled before scoring"
            if index in RATIONALE:
                row["rationale"] = RATIONALE[index]
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    counts = Counter(LABELS.values())
    print(f"seed {args.seed}")
    print(f"labelled {len(candidates)} hypotheses")
    for name, count in counts.most_common():
        print(f"  {name:<24} {count}")
    print()
    print(f"positives {sum(1 for v in LABELS.values() if v != NONE)}")
    print(f"negatives {counts[NONE]}")
    print(f"rationale recorded for {len(RATIONALE)} arguable cases")
    print(f"written {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
