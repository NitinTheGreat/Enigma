#!/usr/bin/env bash
cd "/mnt/f/XAI Project"
export CUDA_VISIBLE_DEVICES=-1
export PYTHONUNBUFFERED=1
exec /opt/enigma/.venv-agent/bin/python "$@"
