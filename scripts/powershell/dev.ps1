# Development server - runs backend and frontend concurrently
# Usage: .\dev.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $ProjectRoot

Write-Host "Starting TQQQ Trading System (Development)" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment
& "$ProjectRoot\venv\Scripts\Activate.ps1"

# Start backend in background
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:ProjectRoot
    & "$using:ProjectRoot\venv\Scripts\python.exe" src/api.py
}

# Start frontend in background
$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:ProjectRoot\frontend"
    npm run dev
}

Write-Host "Backend Job ID: $($backendJob.Id)" -ForegroundColor Cyan
Write-Host "Frontend Job ID: $($frontendJob.Id)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop..." -ForegroundColor Red
Write-Host ""

# Monitor jobs and show output
try {
    while ($true) {
        # Show backend output
        Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        # Show frontend output
        Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue

        # Check if jobs are still running
        if ($backendJob.State -eq "Failed" -or $frontendJob.State -eq "Failed") {
            Write-Host "A job has failed!" -ForegroundColor Red
            break
        }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host "`nShutting down..." -ForegroundColor Red
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job -Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
    Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped." -ForegroundColor Green
}
