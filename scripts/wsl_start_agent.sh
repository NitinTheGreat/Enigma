#!/usr/bin/env bash
AGENT_VENV=/opt/enigma/.venv-agent
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
export PYTHONUNBUFFERED=1
export ENIGMA_LOG_LEVEL=INFO

cd "$PROJ/Enigma-AIAgent"
exec "$AGENT_VENV/bin/python" -m uvicorn enigma_reason.main:app \
  --host 0.0.0.0 --port 8000 --log-level info
