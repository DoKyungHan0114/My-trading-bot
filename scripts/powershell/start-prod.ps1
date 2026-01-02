# TQQQ Trading System - Production Start Script
# Builds frontend and runs FastAPI serving static files
# Usage: .\start-prod.ps1 [-Build]

param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $ProjectRoot

Write-Host "========================================" -ForegroundColor Green
Write-Host "  TQQQ Trading System (Production)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Python is available
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
& "$ProjectRoot\venv\Scripts\Activate.ps1"

# Build frontend if dist doesn't exist or --Build flag
if (!(Test-Path "$ProjectRoot\frontend\dist") -or $Build) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Set-Location "$ProjectRoot\frontend"
    npm install
    npm run build
    Set-Location $ProjectRoot
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Server running on http://localhost:8000" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard: " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Yellow
Write-Host "  API Docs:  " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press " -NoNewline; Write-Host "Ctrl+C" -ForegroundColor Red -NoNewline; Write-Host " to stop"
Write-Host ""

# Run server
try {
    python src/api.py
}
finally {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow

    # Kill any remaining processes on port 8000
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

    Write-Host "Stopped." -ForegroundColor Green
}
