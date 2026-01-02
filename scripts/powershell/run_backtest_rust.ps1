# TQQQ Backtest Runner - Rust Engine + Claude AI Analysis
# Usage: .\run_backtest_rust.ps1 [capital]
# Example: .\run_backtest_rust.ps1 100000
# Auto-apply: $env:AUTO_APPLY="true"; .\run_backtest_rust.ps1

param(
    [int]$Capital = 100000
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Get AUTO_APPLY from environment variable
$AutoApply = if ($env:AUTO_APPLY -eq "true") { $true } else { $false }

$DataFile = "data/tqqq_daily.csv"

# Optimized RSI parameters (found via backtesting)
$RsiOversold = 48
$RsiOverbought = 55

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "TQQQ RSI(2) Mean Reversion Trading System" -ForegroundColor Cyan
Write-Host "           [Rust Engine + Claude AI]" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Data: $DataFile | Capital: `$$Capital" -ForegroundColor White
Write-Host "RSI: $RsiOversold/$RsiOverbought (optimized)" -ForegroundColor White
Write-Host "==============================================" -ForegroundColor Cyan

# Activate virtual environment
& "$PSScriptRoot\venv\Scripts\Activate.ps1"

# Load environment variables from .env file
if (Test-Path "$PSScriptRoot\.env") {
    Get-Content "$PSScriptRoot\.env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Update market data first
Write-Host ""
Write-Host "[Step 0/3] Fetching latest TQQQ data..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

python -c @"
from data.fetcher import DataFetcher
from datetime import datetime, timedelta

fetcher = DataFetcher()
end = datetime.now()
start = end - timedelta(days=365)

df = fetcher.get_daily_bars('TQQQ', start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
df['volume'] = df['volume'].astype(int)
df_export = df[['open', 'high', 'low', 'close', 'volume', 'vwap']].copy()
df_export.index.name = 'timestamp'
df_export.to_csv('$DataFile')
print(f'Updated {len(df)} bars ({df.index[0].date()} to {df.index[-1].date()})')
"@

Write-Host ""
Write-Host "[Step 1/3] Running Rust Backtest Engine..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

# Run Rust backtest and save JSON result
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ResultFile = "reports/rust_backtest_$Timestamp.json"

# Run Rust engine
& "$PSScriptRoot\rust\target\release\backtest-engine.exe" `
    -f $DataFile `
    --capital $Capital `
    --rsi-oversold $RsiOversold `
    --rsi-overbought $RsiOverbought `
    --output json `
    --pretty | Out-File -FilePath $ResultFile -Encoding utf8

Write-Host "Backtest complete! Result saved to: $ResultFile" -ForegroundColor Green

# Also show text summary
& "$PSScriptRoot\rust\target\release\backtest-engine.exe" `
    -f $DataFile `
    --capital $Capital `
    --rsi-oversold $RsiOversold `
    --rsi-overbought $RsiOverbought `
    --output text

Write-Host ""
Write-Host "[Step 2/3] Generating Analysis Report..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

# Generate report for Claude using Rust results
$pythonCode = @"
import json
from pathlib import Path
from reports.report_generator import ReportGenerator
from config.settings import get_settings

# Load Rust backtest result
with open('$ResultFile') as f:
    rust_result = json.load(f)

settings = get_settings()
gen = ReportGenerator(strategy_config=settings.strategy)

# Create report with Rust metrics
report, path = gen.generate_and_save(backtest_metrics=rust_result.get('metrics'))
print(f'Report saved: {path}')
print(f'Rust Engine Execution: {rust_result.get("execution_time_ms", 0)}ms')
print(f'Total Return: {rust_result["metrics"]["total_return_pct"]:.2f}%')
print(f'Sharpe Ratio: {rust_result["metrics"]["sharpe_ratio"]:.3f}')
print(f'Win Rate: {rust_result["metrics"]["win_rate"]:.1f}%')
"@
python -c $pythonCode

Write-Host ""
Write-Host "[Step 3/3] Claude AI Strategy Analysis..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

# Run Claude analysis
if ($AutoApply) {
    Write-Host "Mode: AUTO-APPLY (changes will be saved)" -ForegroundColor Green
    python -m automation.claude_analyzer --auto
} else {
    Write-Host "Mode: REVIEW ONLY (no auto-apply)" -ForegroundColor Cyan
    python -m automation.claude_analyzer
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Complete! (Powered by Rust Engine)" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Outputs:" -ForegroundColor White
Write-Host "  - Rust JSON:  $ResultFile" -ForegroundColor Gray
Write-Host "  - Analysis:   reports/analysis_*.json" -ForegroundColor Gray
Write-Host ""
Write-Host "To auto-apply Claude's suggestions:" -ForegroundColor White
Write-Host '  $env:AUTO_APPLY="true"; .\run_backtest_rust.ps1' -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Cyan
