#!/usr/bin/env bash
cd "/mnt/f/XAI Project/Enigma-AIAgent"
export CUDA_VISIBLE_DEVICES=-1
export PYTHONUNBUFFERED=1
/opt/enigma/.venv-agent/bin/python -m pytest -q 2>&1 | tail -15
