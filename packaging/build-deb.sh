#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v dpkg-deb >/dev/null || { echo 'Build on openKylin with dpkg-deb installed' >&2; exit 2; }
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/usr/share/kylin-memory-bench" "$stage/usr/bin"
cp -R kylin_memory_bench data configs "$stage/usr/share/kylin-memory-bench/"
find "$stage/usr/share/kylin-memory-bench" -type d -name __pycache__ -prune -exec rm -rf {} +
cp run-fixture.sh run-live.sh requirements.txt README.md LICENSE "$stage/usr/share/kylin-memory-bench/"
cat > "$stage/DEBIAN/control" <<'EOF'
Package: kylin-memory-bench
Version: 0.1.0
Section: science
Priority: optional
Architecture: all
Maintainer: Yan Su <hi@yansu.me>
Depends: python3 (>= 3.10), python3-websocket
Description: Evidence-based six-ability long-term memory benchmark for agents
EOF
cat > "$stage/usr/bin/kylin-memory-bench" <<'EOF'
#!/bin/sh
cd /usr/share/kylin-memory-bench || exit 1
exec python3 -m kylin_memory_bench "$@"
EOF
chmod 755 "$stage/usr/bin/kylin-memory-bench"
mkdir -p dist
dpkg-deb --build --root-owner-group "$stage" dist/kylin-memory-bench_0.1.0_all.deb
