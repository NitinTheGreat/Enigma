#!/usr/bin/env bash
ML_VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"

export PYTHONUNBUFFERED=1

cd "$PROJ/Enigma-ML-Layer"

"$ML_VENV/bin/python" Frontend_listener.py &
sleep 1

exec "$ML_VENV/bin/python" Streamer.py \
  --data-dir "$PROJ/data" \
  --uri ws://127.0.0.1:8765 \
  --burst-size 8 \
  --burst-delay 0.4
