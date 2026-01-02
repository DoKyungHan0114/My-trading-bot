#!/bin/bash
# Run single backtest with random 7-day period + Claude auto-apply
# Usage: ./run_random.sh

cd "$(dirname "$0")"
source venv/bin/activate

echo "=============================================="
echo "Random Period Backtest + Claude Analysis"
echo "=============================================="

# Run backtest with random period
python backtest_runner.py --period random --db --pdf

echo ""
echo "[Claude Analysis] Auto-applying changes..."
echo "----------------------------------------------"

# Run Claude analyzer with auto-apply
python -m automation.claude_analyzer --auto

echo ""
echo "=============================================="
echo "Done!"
echo "=============================================="
