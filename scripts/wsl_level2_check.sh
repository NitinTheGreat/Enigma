#!/usr/bin/env bash
AGENT_VENV=/opt/enigma/.venv-agent
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1

echo "=== ruff: Enigma-AIAgent ==="
cd "$PROJ/Enigma-AIAgent"
"$AGENT_VENV/bin/python" -m ruff check enigma_reason tests level2_verify.py 2>&1 | tail -20

echo
echo "=== pytest: Enigma-AIAgent ==="
"$AGENT_VENV/bin/python" -m pytest -q 2>&1 | tail -6

echo
echo "=== pytest: Enigma-ML-Layer ==="
cd "$PROJ/Enigma-ML-Layer"
"$ML_VENV/bin/python" -m pytest -q 2>&1 | tail -6
