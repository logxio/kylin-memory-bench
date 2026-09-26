#!/usr/bin/env bash
set -euo pipefail
output="${1:-out/live-$(date +%Y%m%d-%H%M%S)-$$}"
mkdir -p "$(dirname "$output")"
output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"
cd "$(dirname "$0")"
python3 -m kylin_memory_bench \
  --dataset data/tasks.json \
  --agent configs/kylinbot.example.json \
  --agent configs/openclaw.example.json \
  --output "$output" --max-seconds 1800
