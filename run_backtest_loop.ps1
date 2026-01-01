# Run backtest multiple times with random periods, then Claude analyzes
# Usage: .\run_backtest_loop.ps1 [count]
# Example: .\run_backtest_loop.ps1 10

param(
    [int]$Count = 5
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Activate virtual environment
& "$PSScriptRoot\venv\Scripts\Activate.ps1"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Running $Count random period backtests" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Ensure logs directory exists
if (!(Test-Path "$PSScriptRoot\logs")) {
    New-Item -ItemType Directory -Path "$PSScriptRoot\logs" | Out-Null
}

# Run backtests
for ($i = 1; $i -le $Count; $i++) {
    Write-Host "[$i/$Count] Running backtest..." -ForegroundColor Yellow
    Write-Host "------------------------------------------" -ForegroundColor Gray

    # Run backtest with random period
    python backtest_runner.py --period random --db

    Write-Host ""
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Completed $Count backtests" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Running Claude analysis..." -ForegroundColor Yellow
Write-Host "------------------------------------------" -ForegroundColor Gray

# Run Claude analyzer with auto-apply
python automation/claude_analyzer.py --auto

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Done! Strategy updated if needed." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
