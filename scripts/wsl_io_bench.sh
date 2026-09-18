#!/usr/bin/env bash
set -e
VENV=/opt/enigma/.venv-gpu
PROJ="/mnt/f/XAI Project"
IOBENCH="$PROJ/Enigma-ML-Layer/bench_io.py"
OUT="$PROJ/results/bench"

echo "=== read from /mnt/f (drvfs boundary) ==="
sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
$VENV/bin/python "$IOBENCH" --data-dir "$PROJ/data" --label "mnt_f_drvfs" \
  --drop-caches --output "$OUT/io_mnt_f.json"

echo
echo "=== copying data into WSL filesystem ==="
mkdir -p /opt/enigma/data
COPY_START=$(date +%s.%N)
cp "$PROJ/data/"*.csv /opt/enigma/data/
COPY_END=$(date +%s.%N)
echo "copy seconds: $(echo "$COPY_END - $COPY_START" | bc)"
du -sh /opt/enigma/data

echo
echo "=== read from /opt/enigma/data (native ext4) ==="
sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
$VENV/bin/python "$IOBENCH" --data-dir /opt/enigma/data --label "wsl_ext4" \
  --drop-caches --output "$OUT/io_wsl_ext4.json"
