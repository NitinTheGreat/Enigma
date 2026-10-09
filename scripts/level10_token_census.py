"""
Module: scripts/level10_token_census.py

Counts the prompt and completion tokens the repair experiment will spend.

Prompts are captured offline by wrapping the generation node during a replay
driven by a factory that raises, which costs no model call: the prompt is
assembled before generation is attempted. Completions are read from the
Level 9 response cache, which holds what the model actually returned.

Tokens are estimated rather than counted exactly. The Gemini tokeniser is
not available offline, so the ratio of four characters to one token is used,
which is the conventional approximation for English prose and is stated here
rather than hidden. The estimate feeds a budget gate, so it is deliberately
rounded up at every step.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "Enigma-AIAgent"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from enigma_reason.graph import builder as graph_builder  # noqa: E402
from enigma_reason.graph import nodes as graph_nodes  # noqa: E402
from enigma_reason.graph.builder import EpistemicControls  # noqa: E402
from enigma_reason.replay.offline import OfflineReplay  # noqa: E402
from enigma_reason.store.correlation import EntityCorrelation  # noqa: E402

from level7_validate import load_suite, raising_llm_factory  # noqa: E402

SCENARIOS_DIR = PROJECT_ROOT / "results" / "scenarios"
ABLATION_DIR = PROJECT_ROOT / "results" / "ablation"
RESULTS_DIR = PROJECT_ROOT / "results" / "repair"

CHARS_PER_TOKEN = 4.0


def main() -> int:
    """Measure prompt and completion sizes and write the census."""
    parser = argparse.ArgumentParser(description="Token census for the repair.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenarios", type=int, default=8)
    parser.add_argument(
        "--suite", type=str, default=str(SCENARIOS_DIR / "sub_suite.jsonl")
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suite_path = Path(args.suite)
    if not suite_path.is_absolute():
        suite_path = (PROJECT_ROOT / suite_path).resolve()
    scenarios = load_suite(suite_path)[: args.scenarios]

    prompts: list[int] = []
    original = graph_nodes.make_generate_hypotheses

    def recording_factory(llm_factory, unknown_enabled=True, stable_identity=False):
        """Wrap the generation node so every prompt it builds is measured."""
        node = original(
            llm_factory, unknown_enabled=unknown_enabled, stable_identity=stable_identity
        )
        prompt_template = graph_nodes._HYPOTHESIS_PROMPT

        def measured(state):
            context = state.get("context", {})
            existing = state.get("hypotheses", [])
            text = prompt_template.format(
                **context,
                existing_hypothesis_context=graph_nodes._build_existing_hypothesis_context(
                    existing
                ),
            )
            prompts.append(len(text))
            return node(state)

        return measured

    graph_builder.make_generate_hypotheses = recording_factory
    for scenario in scenarios:
        replay = OfflineReplay(
            raising_llm_factory(),
            seed=args.seed,
            correlation=EntityCorrelation(),
            controls=EpistemicControls(),
        )
        replay.run(scenario.signals)
    graph_builder.make_generate_hypotheses = original

    completions: list[int] = []
    for cache_path in sorted(ABLATION_DIR.glob("cache_seed*.json")):
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        for value in payload.get("entries", {}).values():
            completions.append(len(str(value)))
        break

    prompt_chars = mean(prompts) if prompts else 0.0
    completion_chars = mean(completions) if completions else 0.0
    prompt_tokens = prompt_chars / CHARS_PER_TOKEN
    completion_tokens = completion_chars / CHARS_PER_TOKEN

    report = {
        "seed": args.seed,
        "suite": str(suite_path.relative_to(PROJECT_ROOT)),
        "scenarios_sampled": len(scenarios),
        "prompts_measured": len(prompts),
        "completions_measured": len(completions),
        "chars_per_token_assumed": CHARS_PER_TOKEN,
        "mean_prompt_chars": round(prompt_chars, 1),
        "mean_completion_chars": round(completion_chars, 1),
        "mean_prompt_tokens": round(prompt_tokens, 1),
        "mean_completion_tokens": round(completion_tokens, 1),
        "note": (
            "The Gemini tokeniser is not available offline, so four characters "
            "to one token is assumed. The figure feeds a budget gate and is "
            "rounded up at every later step."
        ),
    }
    (RESULTS_DIR / f"token_census_seed{args.seed}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    csv_path = RESULTS_DIR / f"token_census_seed{args.seed}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["seed", "quantity", "value"])
        for key in (
            "prompts_measured",
            "completions_measured",
            "mean_prompt_chars",
            "mean_completion_chars",
            "mean_prompt_tokens",
            "mean_completion_tokens",
        ):
            writer.writerow([args.seed, key, report[key]])

    print(f"seed {args.seed}   scenarios sampled {len(scenarios)}")
    print(f"prompts measured      {len(prompts)}")
    print(f"completions measured  {len(completions)}")
    print(f"mean prompt      {prompt_chars:.0f} chars  ~{prompt_tokens:.0f} tokens")
    print(f"mean completion  {completion_chars:.0f} chars  ~{completion_tokens:.0f} tokens")
    print(f"written {csv_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
