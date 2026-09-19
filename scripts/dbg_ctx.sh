#!/usr/bin/env bash
set -euo pipefail
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
/opt/enigma/.venv-agent/bin/python - <<'PY' 2>/dev/null
import sys
from pathlib import Path

sys.path.insert(0, "Enigma-AIAgent")
sys.path.insert(0, "scripts")

from enigma_reason.graph import builder as graph_builder
from enigma_reason.graph import nodes as graph_nodes
from enigma_reason.graph.builder import EpistemicControls
from enigma_reason.replay.offline import OfflineReplay
from enigma_reason.store.correlation import EntityCorrelation
from scenarios.generator import scenario_id_from_entity
from level7_validate import load_suite, raising_llm_factory

scenarios = load_suite(Path("results/scenarios/sub_suite.jsonl"))
print("scenarios", len(scenarios))
print("sample entities", scenarios[0].entities[:2])
print("scenario_id_from_entity ->", scenario_id_from_entity(scenarios[0].entities[0]))

captured = []
original = graph_nodes.assemble_context

def rec(state):
    r = original(state)
    captured.append(dict(r["context"]))
    return r

graph_builder.assemble_context = rec
s = scenarios[0]
ent = s.entities[0]
sigs = [x for x in s.signals if str(x.entity) == str(ent)]
print("signals for entity", len(sigs))
replay = OfflineReplay(raising_llm_factory(), seed=42, clock_mode="separated",
                       correlation=EntityCorrelation(), controls=EpistemicControls())
replay.run(sigs)
graph_builder.assemble_context = original
print("captured", len(captured))
if captured:
    print("keys", sorted(captured[0].keys()))
PY
