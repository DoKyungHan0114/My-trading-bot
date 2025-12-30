#!/bin/bash
# TQQQ Backtest Runner - Rust Engine + Claude AI Analysis
# Usage: ./run_backtest_rust.sh [capital]

cd "$(dirname "$0")"

# Default values
CAPITAL="${1:-100000}"
AUTO_APPLY="${AUTO_APPLY:-false}"
DATA_FILE="data/tqqq_daily.csv"

# Optimized RSI parameters (found via backtesting)
RSI_OVERSOLD=48
RSI_OVERBOUGHT=55

echo "=============================================="
echo "TQQQ RSI(2) Mean Reversion Trading System"
echo "           [Rust Engine + Claude AI]"
echo "=============================================="
echo "Data: $DATA_FILE | Capital: \$$CAPITAL"
echo "RSI: $RSI_OVERSOLD/$RSI_OVERBOUGHT (optimized)"
echo "=============================================="

# Activate virtual environment
source venv/bin/activate

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Update market data first
echo ""
echo "[Step 0/3] Fetching latest TQQQ data..."
echo "----------------------------------------------"
python -c "
from data.fetcher import DataFetcher
from datetime import datetime, timedelta

fetcher = DataFetcher()
end = datetime.now()
start = end - timedelta(days=365)

df = fetcher.get_daily_bars('TQQQ', start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
df['volume'] = df['volume'].astype(int)
df_export = df[['open', 'high', 'low', 'close', 'volume', 'vwap']].copy()
df_export.index.name = 'timestamp'
df_export.to_csv('$DATA_FILE')
print(f'Updated {len(df)} bars ({df.index[0].date()} to {df.index[-1].date()})')
"

echo ""
echo "[Step 1/3] Running Rust Backtest Engine..."
echo "----------------------------------------------"

# Run Rust backtest and save JSON result
RESULT_FILE="reports/rust_backtest_$(date +%Y%m%d_%H%M%S).json"
./rust/target/release/backtest-engine \
    -f "$DATA_FILE" \
    --capital "$CAPITAL" \
    --rsi-oversold $RSI_OVERSOLD \
    --rsi-overbought $RSI_OVERBOUGHT \
    --output json \
    --pretty > "$RESULT_FILE"

echo "Backtest complete! Result saved to: $RESULT_FILE"

# Also show text summary
./rust/target/release/backtest-engine \
    -f "$DATA_FILE" \
    --capital "$CAPITAL" \
    --rsi-oversold $RSI_OVERSOLD \
    --rsi-overbought $RSI_OVERBOUGHT \
    --output text

echo ""
echo "[Step 2/3] Generating Analysis Report..."
echo "----------------------------------------------"

# Generate report for Claude using Rust results
python -c "
import json
from pathlib import Path
from reports.report_generator import ReportGenerator
from config.settings import get_settings

# Load Rust backtest result
with open('$RESULT_FILE') as f:
    rust_result = json.load(f)

settings = get_settings()
gen = ReportGenerator(strategy_config=settings.strategy)

# Create report with Rust metrics
report, path = gen.generate_and_save(backtest_metrics=rust_result.get('metrics'))
print(f'Report saved: {path}')
print(f'Rust Engine Execution: {rust_result.get(\"execution_time_ms\", 0)}ms')
print(f'Total Return: {rust_result[\"metrics\"][\"total_return_pct\"]:.2f}%')
print(f'Sharpe Ratio: {rust_result[\"metrics\"][\"sharpe_ratio\"]:.3f}')
print(f'Win Rate: {rust_result[\"metrics\"][\"win_rate\"]:.1f}%')
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
echo "Complete! (Powered by Rust Engine)"
echo "=============================================="
echo "Outputs:"
echo "  - Rust JSON:  $RESULT_FILE"
echo "  - Analysis:   reports/analysis_*.json"
echo ""
echo "To auto-apply Claude's suggestions:"
echo "  AUTO_APPLY=true ./run_backtest_rust.sh"
echo "=============================================="
