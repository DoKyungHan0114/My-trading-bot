# Run single backtest with random 7-day period + Claude auto-apply
# Usage: .\run_random.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Activate virtual environment
& "$PSScriptRoot\venv\Scripts\Activate.ps1"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Random Period Backtest + Claude Analysis" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

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

# Run backtest with random period
python backtest_runner.py --period random --db --pdf

Write-Host ""
Write-Host "[Claude Analysis] Auto-applying changes..." -ForegroundColor Yellow
Write-Host "----------------------------------------------" -ForegroundColor Gray

# Run Claude analyzer with auto-apply
python -m automation.claude_analyzer --auto

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Done!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
