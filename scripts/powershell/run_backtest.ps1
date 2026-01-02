# TQQQ Backtest Runner with Claude AI Analysis
# Usage: .\run_backtest.ps1 [days_back] [capital]
# Example: .\run_backtest.ps1 7 10000
# Auto-apply: $env:AUTO_APPLY="true"; .\run_backtest.ps1

param(
    [int]$DaysBack = 7,
    [int]$Capital = 10000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $ProjectRoot

# Get AUTO_APPLY from environment variable
$AutoApply = if ($env:AUTO_APPLY -eq "true") { $true } else { $false }

# Calculate dates
$EndDate = Get-Date -Format "yyyy-MM-dd"
$StartDate = (Get-Date).AddDays(-$DaysBack).ToString("yyyy-MM-dd")

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "TQQQ RSI(2) Mean Reversion Trading System" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Period: $StartDate to $EndDate ($DaysBack days)" -ForegroundColor White
Write-Host "Capital: `$$Capital" -ForegroundColor White
Write-Host "==============================================" -ForegroundColor Cyan

# Activate virtual environment
& "$ProjectRoot\venv\Scripts\Activate.ps1"

# Load environment variables from .env file
if (Test-Path "$ProjectRoot\.env") {
    Get-Content "$ProjectRoot\.env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Write-Host ""
Write-Host "[Step 1/3] Running Backtest..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

# Run backtest with PDF generation and Firestore saving
python src/backtest_runner.py --start $StartDate --end $EndDate --capital $Capital --pdf --db

Write-Host ""
Write-Host "[Step 2/3] Generating Analysis Report..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

# Generate report for Claude
python -c @"
from reports.report_generator import ReportGenerator
from config.settings import get_settings

settings = get_settings()
gen = ReportGenerator(strategy_config=settings.strategy)
report, path = gen.generate_and_save()
print(f'Report saved: {path}')
print(f'Market: {report.market_condition}')
print(f'Context: {report.recommendations_context}')
"@

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
Write-Host "Complete!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Outputs:" -ForegroundColor White
Write-Host "  - PDF report: reports/pdf/backtest_report_*.pdf" -ForegroundColor Gray
Write-Host "  - JSON data:  reports/backtest_*.json" -ForegroundColor Gray
Write-Host "  - Analysis:   reports/analysis_*.json" -ForegroundColor Gray
Write-Host ""
Write-Host "Firestore Collections:" -ForegroundColor White
Write-Host "  - tqqq_strategies  (strategy versions)" -ForegroundColor Gray
Write-Host "  - tqqq_sessions    (backtest results)" -ForegroundColor Gray
Write-Host "  - tqqq_trades      (trade history)" -ForegroundColor Gray
Write-Host "  - tqqq_strategy_changes (AI modifications)" -ForegroundColor Gray
Write-Host ""
Write-Host "To auto-apply Claude's suggestions:" -ForegroundColor White
Write-Host '  $env:AUTO_APPLY="true"; .\run_backtest.ps1' -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Cyan
