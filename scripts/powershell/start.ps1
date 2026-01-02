# TQQQ Trading System - Start Script
# Runs both FastAPI backend and React frontend
# Usage: .\start.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $ProjectRoot

Write-Host "========================================" -ForegroundColor Green
Write-Host "  TQQQ Trading System Dashboard" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Python is available
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed" -ForegroundColor Red
    exit 1
}

# Check if npm is available
if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Error: npm is not installed" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
& "$ProjectRoot\venv\Scripts\Activate.ps1"

# Install frontend dependencies if needed
if (!(Test-Path "$ProjectRoot\frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location "$ProjectRoot\frontend"
    npm install
    Set-Location $ProjectRoot
}

# Start Backend (FastAPI) in background
Write-Host "Starting Backend API on http://localhost:8000" -ForegroundColor Green
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:ProjectRoot
    & "$using:ProjectRoot\venv\Scripts\python.exe" src/api.py
}

# Wait for backend to start
Start-Sleep -Seconds 2

# Start Frontend (Vite dev server) in background
Write-Host "Starting Frontend on http://localhost:5173" -ForegroundColor Green
$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:ProjectRoot\frontend"
    npm run dev
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Dashboard is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend: " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Yellow
Write-Host "  Backend:  " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Yellow
Write-Host "  API Docs: " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press " -NoNewline; Write-Host "Ctrl+C" -ForegroundColor Red -NoNewline; Write-Host " to stop"
Write-Host ""

# Monitor jobs and show output
try {
    while ($true) {
        Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue

        if ($backendJob.State -eq "Failed" -or $frontendJob.State -eq "Failed") {
            Write-Host "A job has failed!" -ForegroundColor Red
            break
        }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host ""
    Write-Host "Shutting down..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job -Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
    Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue

    # Kill any remaining processes on the ports
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

    Write-Host "Stopped." -ForegroundColor Green
}
