#!/usr/bin/env bash
# ==============================================================================
# Rising Star Trend Engine - Standalone Nightly Market Scan Script
# Can be run via local cron, cloud runner, or terminal.
# Usage: ./scripts/run_nightly_scan.sh [--sp500 | --watchlist] [--limit N]
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "======================================================================"
echo " Starting Rising Star Nightly Quant Scan: $(date -u)"
echo " Workspace: $ROOT_DIR"
echo "======================================================================"

# Activate virtual environment if present
if [ -d "venv" ]; then
    echo "[INFO] Activating virtual environment 'venv'..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "[INFO] Activating virtual environment '.venv'..."
    source .venv/bin/activate
fi

# Check Python version
python3 --version || { echo "[ERROR] Python 3 not found."; exit 1; }

# Run verification test suite first
echo "[INFO] Running core engine unit tests..."
python3 -m pytest tests/ -q || {
    echo "[WARNING] Tests reported issues, proceeding with scan cautiously..."
}

# Run scan with forwarded arguments or defaults
SCAN_ARGS="$@"
if [ -z "$SCAN_ARGS" ]; then
    SCAN_ARGS="--sp500 --equity 100000 --risk-pct 1.0"
fi

echo "[INFO] Running: python3 main.py $SCAN_ARGS"
python3 main.py $SCAN_ARGS

echo "======================================================================"
echo " Nightly Quant Scan Completed Successfully: $(date -u)"
echo " Artifacts generated: scan_results.json, scan_results.csv, portfolio.json"
echo "======================================================================"
