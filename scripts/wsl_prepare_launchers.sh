#!/usr/bin/env bash
PROJ="/mnt/f/XAI Project"
mkdir -p /opt/enigma/bin

for name in wsl_start_agent wsl_start_sensor wsl_start_stream; do
  tr -d '\r' < "$PROJ/scripts/$name.sh" > "/opt/enigma/bin/$name.sh"
  chmod +x "/opt/enigma/bin/$name.sh"
done

ls -1 /opt/enigma/bin/
