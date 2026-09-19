#!/usr/bin/env bash
set -euo pipefail
/opt/enigma/.venv-agent/bin/python -m pip install --quiet matplotlib==3.10.7
/opt/enigma/.venv-agent/bin/pip list 2>/dev/null | grep -iE '^matplotlib'
