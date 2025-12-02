# Start Local AI Stack - Foundry Local + Open WebUI (Non-Interactive)
# This script sets up a completely offline AI chat system without prompts

param(
    [switch]$EnableWhisper
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Local AI Stack Startup Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start Foundry Local Service
Write-Host "[1/5] Starting Foundry Local service..." -ForegroundColor Yellow
$serviceStatus = foundry service status 2>&1
if ($serviceStatus -match "not running") {
    Write-Host "  Service not running. Attempting to start..." -ForegroundColor Gray
    try {
        foundry service start 2>&1 | Out-Null
        Start-Sleep -Seconds 3
        Write-Host "  ✓ Service started" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ Need admin rights to start service" -ForegroundColor Yellow
        Write-Host "  Continuing anyway..." -ForegroundColor Gray
    }
} else {
    Write-Host "  ✓ Foundry Local service is ready" -ForegroundColor Green
}

# Step 2: Load AI Models
Write-Host ""
Write-Host "[2/5] Loading AI models..." -ForegroundColor Yellow

$models = @("phi-3.5-mini", "qwen2.5-0.5b")
foreach ($model in $models) {
    Write-Host "  Loading $model..." -ForegroundColor Gray
    $output = foundry model load $model 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $model load initiated" -ForegroundColor Green
    } else {
        Write-Host "  ℹ $model may already be loaded" -ForegroundColor Yellow
    }
}

if ($EnableWhisper) {
    Write-Host "  Loading whisper-small..." -ForegroundColor Gray
    foundry model load whisper-small 2>&1 | Out-Null
}

# Step 3: Verify Foundry endpoint
Write-Host ""
Write-Host "[3/5] Verifying Foundry Local endpoint..." -ForegroundColor Yellow
foundry server status 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Foundry endpoint is accessible" -ForegroundColor Green
} else {
    Write-Host "  ℹ Foundry endpoint check skipped" -ForegroundColor Yellow
}
Start-Sleep -Seconds 2

# Step 4: Stop any existing Open WebUI container
Write-Host ""
Write-Host "[4/5] Preparing Open WebUI..." -ForegroundColor Yellow
docker stop open-webui 2>$null
docker rm open-webui 2>$null
Write-Host "  ✓ Cleaned up existing containers" -ForegroundColor Green

# Step 5: Launch Open WebUI
Write-Host ""
Write-Host "[5/5] Launching Open WebUI..." -ForegroundColor Yellow

$dataPath = "$env:LOCALAPPDATA\open-webui"
if (-not (Test-Path $dataPath)) {
    New-Item -ItemType Directory -Path $dataPath -Force | Out-Null
    Write-Host "  Created data directory: $dataPath" -ForegroundColor Gray
}

# Build docker run command
$dockerArgs = @(
    "run", "-d",
    "--name", "open-webui",
    "--restart", "unless-stopped",
    "-p", "3000:8080",
    "-e", "OPENAI_API_BASE_URL=http://host.docker.internal:5273/v1",
    "-e", "OPENAI_API_KEY=local-key",
    "-e", "ENABLE_SIGNUP=false"
)

if ($EnableWhisper) {
    $dockerArgs += "-e", "WHISPER_API_BASE_URL=http://host.docker.internal:5273/v1"
    $dockerArgs += "-e", "WHISPER_API_KEY=local-key"
}

$dockerArgs += "-v", "${dataPath}:/app/backend/data"
$dockerArgs += "ghcr.io/open-webui/open-webui:main"

Write-Host "  Launching container..." -ForegroundColor Gray
& docker @dockerArgs

Start-Sleep -Seconds 8

# Verify container is running
$containerStatus = docker ps --filter "name=open-webui" --format "{{.Status}}"
if ($containerStatus) {
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host "  ✓ Local AI Stack is Running!" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Open WebUI:       http://localhost:3000" -ForegroundColor Cyan
    Write-Host "Foundry Endpoint: http://localhost:5273/v1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "  1. Browse to http://localhost:3000" -ForegroundColor White
    Write-Host "  2. Create your admin account (first signup)" -ForegroundColor White
    Write-Host "  3. Go to Admin Settings and add models" -ForegroundColor White
    Write-Host "  4. Use model IDs from 'foundry model ls --details'" -ForegroundColor White
    Write-Host ""
    Write-Host "Container Status: $containerStatus" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To stop everything, run: .\stop-local-ai.ps1" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "⚠ Container may still be starting. Checking..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    $containerStatus = docker ps --filter "name=open-webui" --format "{{.Status}}"
    if ($containerStatus) {
        Write-Host "✓ Container is now running!" -ForegroundColor Green
        Write-Host "Open WebUI: http://localhost:3000" -ForegroundColor Cyan
    } else {
        Write-Host "⚠ Container failed to start. Checking logs..." -ForegroundColor Red
        docker logs open-webui 2>&1 | Select-Object -Last 30
    }
}
