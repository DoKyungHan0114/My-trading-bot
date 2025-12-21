#!/bin/bash
# TQQQ Backtest Runner with Claude AI Analysis
# Usage: ./run_backtest.sh [days_back] [capital]

cd "$(dirname "$0")"

# Default values
DAYS_BACK="${1:-7}"
CAPITAL="${2:-10000}"
AUTO_APPLY="${AUTO_APPLY:-false}"

# Calculate dates (last N days)
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -d "$DAYS_BACK days ago" +%Y-%m-%d)

echo "=============================================="
echo "TQQQ RSI(2) Mean Reversion Trading System"
echo "=============================================="
echo "Period: $START_DATE to $END_DATE ($DAYS_BACK days)"
echo "Capital: \$$CAPITAL"
echo "=============================================="

# Activate virtual environment
source venv/bin/activate

# Install missing packages if needed
pip install pyarrow matplotlib --quiet 2>/dev/null

# Load environment variables
export $(grep -v '^#' .env | xargs)

echo ""
echo "[Step 1/3] Running Backtest..."
echo "----------------------------------------------"

# Run backtest with PDF generation and Firestore saving
python backtest_runner.py \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --capital "$CAPITAL" \
    --pdf \
    --db

echo ""
echo "[Step 2/3] Generating Analysis Report..."
echo "----------------------------------------------"

# Generate report for Claude
python -c "
from reports.report_generator import ReportGenerator
from config.settings import get_settings

settings = get_settings()
gen = ReportGenerator(strategy_config=settings.strategy)
report, path = gen.generate_and_save()
print(f'Report saved: {path}')
print(f'Market: {report.market_condition}')
print(f'Context: {report.recommendations_context}')
"

echo ""
echo "[Step 3/3] Claude AI Strategy Analysis..."
echo "----------------------------------------------"

# Run Claude analysis
if [ "$AUTO_APPLY" = "true" ]; then
    echo "Mode: AUTO-APPLY (changes will be saved)"
    python -m automation.claude_analyzer --auto
else
    echo "Mode: REVIEW ONLY (no auto-apply)"
    python -m automation.claude_analyzer
fi

echo ""
echo "=============================================="
echo "Complete!"
echo "=============================================="
echo "Outputs:"
echo "  - PDF report: reports/pdf/backtest_report_*.pdf"
echo "  - JSON data:  reports/backtest_*.json"
echo "  - Analysis:   reports/analysis_*.json"
echo ""
echo "Firestore Collections:"
echo "  - tqqq_strategies  (strategy versions)"
echo "  - tqqq_sessions    (backtest results)"
echo "  - tqqq_trades      (trade history)"
echo "  - tqqq_strategy_changes (AI modifications)"
echo ""
echo "To auto-apply Claude's suggestions:"
echo "  AUTO_APPLY=true ./run_backtest.sh"
echo "=============================================="
