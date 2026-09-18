#!/usr/bin/env bash
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export CUDA_VISIBLE_DEVICES=-1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1

cd "$PROJ/Enigma-ML-Layer"
exec "$ML_VENV/bin/python" main.py \
  --artifacts-dir "$PROJ/artifacts/sensitivity_minimal" \
  --config openset \
  --port 8765 \
  --downstream-uri ws://127.0.0.1:8000/ws/signal \
  --normal-traffic-uri ws://127.0.0.1:9000
