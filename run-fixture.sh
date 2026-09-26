#!/usr/bin/env bash
set -euo pipefail
output="${1:-out/fixture-$(date +%Y%m%d-%H%M%S)-$$}"
mkdir -p "$(dirname "$output")"
output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"
cd "$(dirname "$0")"
python3 -m kylin_memory_bench \
  --dataset data/tasks.json \
  --agent configs/fixture-reference.json \
  --agent configs/fixture-faulty.json \
  --output "$output" --max-seconds 240
