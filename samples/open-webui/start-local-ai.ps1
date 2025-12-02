# Start Local AI Stack - Foundry Local + Open WebUI
# This script sets up a completely offline AI chat system

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Local AI Stack Startup Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start Foundry Local Service
Write-Host "[1/5] Starting Foundry Local service..." -ForegroundColor Yellow
try {
    $serviceStatus = foundry service status 2>&1
    if ($serviceStatus -match "not running") {
        Write-Host "  Service not running. Attempting to start..." -ForegroundColor Gray
        foundry service start
        Start-Sleep -Seconds 3
        $serviceStatus = foundry service status 2>&1
    }
    Write-Host "  ✓ Foundry Local service is ready" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ Could not start service automatically (may need admin rights)" -ForegroundColor Red
    Write-Host "  Please run in an elevated PowerShell: foundry service start" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter after starting the service manually"
}

# Step 2: Load AI Models
Write-Host ""
Write-Host "[2/5] Loading AI models..." -ForegroundColor Yellow

$models = @("phi-3.5-mini", "qwen2.5-0.5b")
foreach ($model in $models) {
    Write-Host "  Loading $model..." -ForegroundColor Gray
    try {
        foundry model load $model
        Write-Host "  ✓ $model loaded" -ForegroundColor Green
    } catch {
        Write-Host "  ℹ $model may already be loaded or downloading" -ForegroundColor Yellow
    }
}

# Optional: Load Whisper for speech-to-text
$loadWhisper = Read-Host "`nLoad Whisper model for speech-to-text? (y/N)"
if ($loadWhisper -eq "y" -or $loadWhisper -eq "Y") {
    Write-Host "  Loading whisper-small..." -ForegroundColor Gray
    foundry model load whisper-small
    $enableWhisper = $true
} else {
    $enableWhisper = $false
}

# Step 3: Verify Foundry endpoint
Write-Host ""
Write-Host "[3/5] Verifying Foundry Local endpoint..." -ForegroundColor Yellow
foundry server status
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

if ($enableWhisper) {
    $dockerArgs += "-e", "WHISPER_API_BASE_URL=http://host.docker.internal:5273/v1"
    $dockerArgs += "-e", "WHISPER_API_KEY=local-key"
}

$dockerArgs += "-v", "${dataPath}:/app/backend/data"
$dockerArgs += "ghcr.io/open-webui/open-webui:main"

& docker @dockerArgs

Start-Sleep -Seconds 5

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
    Write-Host "Loaded Models:" -ForegroundColor Yellow
    foundry model ls
    Write-Host ""
    Write-Host "To stop everything, run: .\stop-local-ai.ps1" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "⚠ Container failed to start. Checking logs..." -ForegroundColor Red
    docker logs open-webui
}
