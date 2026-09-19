#!/usr/bin/env bash
set -euo pipefail
PY=/opt/enigma/.venv-agent/bin/python
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
$PY -m pip install --quiet sentence-transformers==5.1.0
echo "--- installed ---"
$PY -m pip list 2>/dev/null | grep -iE '^torch |sentence-transformers|^transformers |^numpy '
