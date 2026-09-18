#!/usr/bin/env bash
AGENT_VENV=/opt/enigma/.venv-agent
PROJ="/mnt/f/XAI Project"
cd "$PROJ/Enigma-AIAgent"

DUMP=$(cat <<'PY'
from enigma_reason.config import Settings
from enigma_reason.graph.builder import EpistemicControls, build_reasoning_graph

settings = Settings()
controls = EpistemicControls(
    unknown_hypothesis_enabled=settings.unknown_hypothesis_enabled,
    sanity_gate_enabled=settings.sanity_gate_enabled,
    asymmetric_decay_enabled=settings.asymmetric_decay_enabled,
    persistence_required=settings.persistence_required,
    max_confidence_delta=settings.max_confidence_delta,
)
graph = build_reasoning_graph(lambda: None, controls)
nodes = sorted(n for n in graph.get_graph().nodes if n not in ("__start__", "__end__"))
print("ENIGMA_CLOCK_MODE                 =", settings.clock_mode.value)
print("ENIGMA_UNKNOWN_HYPOTHESIS_ENABLED =", settings.unknown_hypothesis_enabled)
print("ENIGMA_SANITY_GATE_ENABLED        =", settings.sanity_gate_enabled)
print("ENIGMA_ASYMMETRIC_DECAY_ENABLED   =", settings.asymmetric_decay_enabled)
print("ENIGMA_PERSISTENCE_REQUIRED       =", settings.persistence_required)
print("ENIGMA_MAX_CONFIDENCE_DELTA       =", settings.max_confidence_delta)
print("graph nodes                       =", nodes)
PY
)

echo "=== defaults ==="
"$AGENT_VENV/bin/python" -c "$DUMP"

echo
echo "=== all switches disabled via environment ==="
ENIGMA_CLOCK_MODE=conflated \
ENIGMA_UNKNOWN_HYPOTHESIS_ENABLED=false \
ENIGMA_SANITY_GATE_ENABLED=false \
ENIGMA_ASYMMETRIC_DECAY_ENABLED=false \
ENIGMA_PERSISTENCE_REQUIRED=false \
ENIGMA_MAX_CONFIDENCE_DELTA=inf \
"$AGENT_VENV/bin/python" -c "$DUMP"
