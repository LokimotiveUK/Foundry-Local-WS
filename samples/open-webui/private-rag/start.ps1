# start.ps1 - Start the entire RAG stack
#
# This script:
# 1. Checks if Foundry Local is running
# 2. Starts the Foundry Proxy (fixed port 5999 -> dynamic Foundry port)
# 3. Starts Docker containers
# 4. Verifies everything works
#
# Usage:
#   ./start.ps1           # Start everything
#   ./start.ps1 -Stop     # Stop everything
#   ./start.ps1 -Restart  # Restart everything

param(
    [switch]$Stop,
    [switch]$Restart,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step($msg) { Write-Host "`n[$msg]" -ForegroundColor Cyan }
function Write-OK($msg) { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  FAIL: $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "  $msg" -ForegroundColor Gray }

# Stop everything
function Stop-All {
    Write-Step "Stopping services"

    # Stop proxy
    $proxyJobs = Get-Job -Name "FoundryProxy" -ErrorAction SilentlyContinue
    if ($proxyJobs) {
        $proxyJobs | Stop-Job -PassThru | Remove-Job
        Write-OK "Stopped Foundry Proxy"
    }

    # Also try to kill any running proxy process
    Get-Process -Name "python*" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*foundry-proxy*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue

    # Stop Docker containers
    Push-Location $scriptDir
    docker compose down 2>&1 | Out-Null
    Pop-Location
    Write-OK "Stopped Docker containers"
}

if ($Stop) {
    Stop-All
    exit 0
}

if ($Restart) {
    Stop-All
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting RAG Stack" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Check Foundry
Write-Step "1. Checking Foundry Local"
$foundryStatus = & foundry service status 2>&1 | Out-String
if ($foundryStatus -match "not running") {
    Write-Fail "Foundry Local is not running!"
    Write-Host ""
    Write-Host "  Please start Foundry first:" -ForegroundColor Yellow
    Write-Host "    foundry service start" -ForegroundColor White
    Write-Host ""
    exit 1
}

if ($foundryStatus -match "http://[^:]+:(\d+)") {
    $foundryPort = $Matches[1]
    Write-OK "Foundry running on port $foundryPort"
} else {
    Write-Fail "Could not detect Foundry port"
    exit 1
}

# Step 2: Start Foundry Proxy
Write-Step "2. Starting Foundry Proxy"

# Check if proxy already running
$proxyTest = $null
try {
    $proxyTest = Invoke-RestMethod -Uri "http://localhost:5999/v1/models" -TimeoutSec 2 -ErrorAction SilentlyContinue
} catch {}

if ($proxyTest) {
    Write-OK "Proxy already running on port 5999"
} else {
    # Start proxy as background job
    $proxyScript = Join-Path $scriptDir "foundry-proxy.py"

    Start-Process -FilePath "python" -ArgumentList $proxyScript -WindowStyle Hidden -PassThru | Out-Null

    # Wait for proxy to start
    Write-Info "Waiting for proxy to start..."
    $maxWait = 10
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 1
        $waited++
        try {
            $test = Invoke-RestMethod -Uri "http://localhost:5999/v1/models" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($test) {
                Write-OK "Proxy started on port 5999"
                break
            }
        } catch {}
    }

    if ($waited -ge $maxWait) {
        Write-Fail "Proxy failed to start"
        exit 1
    }
}

# Step 3: Start Docker containers
Write-Step "3. Starting Docker containers"
Push-Location $scriptDir

$composeArgs = @("compose", "up", "-d")
if (-not $NoBuild) {
    $composeArgs += "--build"
}

docker @composeArgs 2>&1 | Out-Null
Pop-Location

# Wait for RAG server
Write-Info "Waiting for RAG server to be healthy..."
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    $waited += 2
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($health.status -eq "healthy") {
            Write-OK "RAG server healthy"
            break
        }
    } catch {}
    Write-Host "." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if ($waited -ge $maxWait) {
    Write-Fail "RAG server did not become healthy"
    Write-Host "  Check logs: docker logs rag-server" -ForegroundColor Yellow
}

# Step 4: Verify end-to-end
Write-Step "4. Verifying end-to-end connectivity"

try {
    $testQuery = @{
        query = "test"
        top_k = 1
    } | ConvertTo-Json

    $result = Invoke-RestMethod -Uri "http://localhost:8000/search" -Method Post -ContentType "application/json" -Body $testQuery -TimeoutSec 30
    Write-OK "RAG server can query documents"
} catch {
    Write-Fail "End-to-end test failed: $_"
}

# Done!
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  RAG Stack Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Services:" -ForegroundColor White
Write-Host "    Open WebUI:      http://localhost:3000" -ForegroundColor Cyan
Write-Host "    RAG Admin:       http://localhost:8501" -ForegroundColor Cyan
Write-Host "    RAG API:         http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "    Foundry Proxy:   http://localhost:5999 -> :$foundryPort" -ForegroundColor Gray
Write-Host ""
Write-Host "  The proxy handles Foundry's dynamic ports automatically." -ForegroundColor Gray
Write-Host "  If Foundry restarts, the proxy will detect the new port." -ForegroundColor Gray
Write-Host ""
Write-Host "  Test command:" -ForegroundColor Yellow
Write-Host '  curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d "{\"query\":\"summarize my resume\",\"category\":\"job-search\"}"' -ForegroundColor Gray
Write-Host ""
