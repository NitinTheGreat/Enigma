#!/usr/bin/env bash
set -e
AGENT_VENV=/opt/enigma/.venv-agent
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
cd "$PROJ/Enigma-AIAgent"

"$AGENT_VENV/bin/python" level2_verify.py --seed 42 --signals 400
