#!/bin/bash
set -euo pipefail

export MSYS_NO_PATHCONV=1

SCRIPT_NAME=${1:-}
RESULT_DIR="$(dirname "$0")/results"
METRICS_FILE="$RESULT_DIR/docker_metrics.csv"
K6_RESULT="$RESULT_DIR/k6_result.json"

if [ -z "$SCRIPT_NAME" ]; then
  echo "❌ Vui lòng truyền tên file k6: ./run_test_with_metrics.sh script.js"
  exit 1
fi

mkdir -p "$RESULT_DIR"
chmod 777 "$RESULT_DIR"
: > "$METRICS_FILE"

echo "👉 Running k6 test: $SCRIPT_NAME"
echo "👉 Results directory: $RESULT_DIR"
echo "👉 Metrics file     : $METRICS_FILE"
echo "👉 k6 summary file  : $K6_RESULT"

echo "timestamp,container,cpu_percent,mem_usage" > "$METRICS_FILE"

# ---- Thu thập metrics CPU/RAM ----
collect_stats() {
  while true; do
    TS=$(date +%s)
    docker stats --no-stream --format "$TS,{{.Name}},{{.CPUPerc}},{{.MemUsage}}" \
      | grep -E "postgres|kafka|order|inventory|api" >> "$METRICS_FILE" || true
    sleep 0.5
  done
}
collect_stats &
STATS_PID=$!

cleanup() {
  echo "🧹 Stopping stats collector (PID $STATS_PID)..."
  kill "$STATS_PID" 2>/dev/null || true
}
trap cleanup EXIT

# ---- Build k6 image (dùng Dockerfile trong folder test) ----
echo "⚙️  Building custom k6 image..."
docker build -t myk6:test .

# ---- Run k6 container trong network qc_tt ----
echo "⚙️  Starting k6 test container in network qc_tt..."
docker run --rm \
  --network=qc_tt \
  -v "$RESULT_DIR":/results \
  -v "$(pwd)":/test \
  myk6:test run "/test/$SCRIPT_NAME" \
  --summary-export="/results/k6_result.json"
echo "PWD on host: $(pwd)"
echo "SCRIPT_NAME: $SCRIPT_NAME"
echo "RESULT_DIR : $RESULT_DIR"
# ---- Verify ----
echo "✅ k6 finished. Verifying output files..."
ls -la "$RESULT_DIR" || true

echo "✅ Docker metrics saved to $METRICS_FILE"
if [ -f "$K6_RESULT" ]; then
  echo "✅ k6 summary saved to $K6_RESULT"
else
  echo "❌ Không thấy $K6_RESULT. Kiểm tra lại volume mount './results:/results'."
fi
