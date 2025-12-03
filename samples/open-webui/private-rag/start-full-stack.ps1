# Start Full Private RAG Stack with Admin UI
# Launches everything via Docker Compose

param(
    [switch]$Build,
    [switch]$Detached
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Private RAG Stack - Full Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker is running
Write-Host "[1/4] Checking Docker..." -ForegroundColor Yellow
try {
    docker info 2>&1 | Out-Null
    Write-Host "  Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check Foundry Local is running
Write-Host ""
Write-Host "[2/4] Checking Foundry Local..." -ForegroundColor Yellow
try {
    $foundryStatus = foundry service status 2>&1
    if ($foundryStatus -match "http://[^:]+:(\d+)") {
        $foundryPort = $Matches[1]
        Write-Host "  Foundry Local running on port $foundryPort" -ForegroundColor Green
    } else {
        Write-Host "  Starting Foundry Local..." -ForegroundColor Gray
        foundry service start
        Start-Sleep -Seconds 3
        $foundryStatus = foundry service status 2>&1
        if ($foundryStatus -match "http://[^:]+:(\d+)") {
            $foundryPort = $Matches[1]
            Write-Host "  Foundry Local started on port $foundryPort" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "  WARNING: Could not check Foundry status. RAG queries may fail." -ForegroundColor Yellow
}

# Build and start containers
Write-Host ""
Write-Host "[3/4] Starting Docker containers..." -ForegroundColor Yellow
Push-Location $scriptDir

$composeArgs = @("compose", "up")
if ($Build) {
    $composeArgs += "--build"
}
if ($Detached) {
    $composeArgs += "-d"
}

if ($Detached) {
    docker @composeArgs
    Write-Host "  Containers started in background" -ForegroundColor Green
} else {
    Write-Host "  Starting containers (press Ctrl+C to stop)..." -ForegroundColor Gray
    Write-Host ""
}

Pop-Location

# Show status
Write-Host ""
Write-Host "[4/4] Stack Status" -ForegroundColor Yellow
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Private RAG Stack Ready!" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Services:" -ForegroundColor White
Write-Host "    Qdrant Dashboard:  http://localhost:6333/dashboard" -ForegroundColor Gray
Write-Host "    RAG API Server:    http://localhost:8000" -ForegroundColor Gray
Write-Host "    RAG Admin UI:      http://localhost:8501" -ForegroundColor Green
Write-Host "    Open WebUI:        http://localhost:3000" -ForegroundColor Gray
Write-Host ""
Write-Host "  Quick Links:" -ForegroundColor White
Write-Host "    Upload documents:  http://localhost:8501" -ForegroundColor Gray
Write-Host "    API docs:          http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""

if (-not $Detached) {
    Push-Location $scriptDir
    docker compose up
    Pop-Location
}
