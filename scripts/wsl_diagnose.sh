#!/usr/bin/env bash
VENV=/opt/enigma/.venv-gpu

echo "=== python ==="
$VENV/bin/python --version

echo "=== tensorflow import ==="
$VENV/bin/python - <<'PY'
try:
    import tensorflow as tf
    print("tensorflow", tf.__version__)
except Exception as exc:
    print("tensorflow import failed:", type(exc).__name__, exc)
PY

echo "=== installed nvidia packages ==="
$VENV/bin/python -m pip list 2>/dev/null | grep -i -E "nvidia|tensorflow|keras" || echo "none"

echo "=== openssl / ca ==="
openssl version
ls -la /etc/ssl/certs/ca-certificates.crt 2>&1 | head -2

echo "=== pypi tls probe ==="
echo | openssl s_client -connect files.pythonhosted.org:443 -servername files.pythonhosted.org 2>&1 | grep -E "subject=|issuer=|Verify return code|verify error" | head -10

echo "=== curl probe ==="
curl -sS -o /dev/null -w "curl http code: %{http_code}\n" https://files.pythonhosted.org/ 2>&1 | head -5
