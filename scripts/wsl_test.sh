#!/usr/bin/env bash
AGENT_VENV=/opt/enigma/.venv-agent
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
cd "$PROJ/Enigma-AIAgent"

"$AGENT_VENV/bin/python" -m pytest -q --tb=short "$@"
