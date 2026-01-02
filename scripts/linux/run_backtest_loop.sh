#!/bin/bash
# Run backtest multiple times with random periods, then Claude analyzes
# Usage: ./run_backtest_loop.sh [count]
# Example: ./run_backtest_loop.sh 10

COUNT=${1:-5}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

echo "=========================================="
echo "Running $COUNT random period backtests"
echo "=========================================="
echo ""

# Store results
RESULTS_FILE="$SCRIPT_DIR/logs/backtest_results.json"
echo "[" > "$RESULTS_FILE"

for i in $(seq 1 $COUNT); do
    echo "[$i/$COUNT] Running backtest..."
    echo "------------------------------------------"
    
    # Run backtest and capture output
    python backtest_runner.py --period random --db
    
    echo ""
done

echo "=========================================="
echo "Completed $COUNT backtests"
echo "=========================================="
echo ""
echo "Running Claude analysis..."
echo "------------------------------------------"

# Run Claude analyzer with auto-apply
python automation/claude_analyzer.py --auto

echo ""
echo "=========================================="
echo "Done! Strategy updated if needed."
echo "=========================================="
