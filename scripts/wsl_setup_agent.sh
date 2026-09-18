#!/usr/bin/env bash
set -e
AGENT_VENV=/opt/enigma/.venv-agent
PROJ="/mnt/f/XAI Project"

if [ ! -d "$AGENT_VENV" ]; then
  python3 -m venv "$AGENT_VENV"
  "$AGENT_VENV/bin/python" -m pip install --upgrade pip setuptools wheel -q
fi

"$AGENT_VENV/bin/python" -m pip install -q --retries 10 --timeout 120 \
  -r "$PROJ/Enigma-AIAgent/requirements.txt"

echo "=== versions ==="
"$AGENT_VENV/bin/python" -m pip list 2>/dev/null | grep -i -E "^fastapi|^langgraph|^langchain-core|^pydantic |^pytest |^ormsgpack" || true

echo "=== import check ==="
cd "$PROJ/Enigma-AIAgent"
"$AGENT_VENV/bin/python" -c "import enigma_reason.main; print('app imports ok')"
