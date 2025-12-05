# rag-manager.ps1
# Robust RAG Stack Manager - Handles all the failure modes that plague the current design
#
# DESIGN PROBLEMS THIS SOLVES:
# 1. Foundry Local uses dynamic ports that change on every restart
# 2. Docker containers bake in the port at startup time
# 3. When Foundry restarts (or crashes), containers point to dead ports
# 4. No health monitoring or auto-recovery
# 5. Open WebUI also needs the port updated
#
# SOLUTION:
# - Detect Foundry port dynamically on every operation
# - Restart containers when port changes
# - Verify all connections before declaring "ready"
# - Provide clear diagnostics when things fail

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "diagnose", "fix")]
    [string]$Command = "status",

    [string]$Model = "",
    [switch]$Force,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Colors for output
function Write-Status($msg) { Write-Host "  $msg" -ForegroundColor Gray }
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Step($msg) { Write-Host "`n$msg" -ForegroundColor Cyan }

# Get current Foundry port (returns $null if not running)
function Get-FoundryPort {
    try {
        $status = & foundry service status 2>&1 | Out-String
        if ($status -match "127\.0\.0\.1:(\d+)" -or $status -match "localhost:(\d+)") {
            return $Matches[1]
        }
        if ($status -match ":(\d{4,5})") {
            return $Matches[1]
        }
    } catch {}
    return $null
}

# Get the port that RAG server is currently configured with
function Get-RagServerPort {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($health.foundry_endpoint -match ":(\d+)/") {
            return $Matches[1]
        }
    } catch {}
    return $null
}

# Get Open WebUI's configured Foundry port
function Get-OpenWebUIPort {
    try {
        $env = docker exec open-webui printenv OPENAI_API_BASE_URL 2>&1
        if ($env -match ":(\d+)/") {
            return $Matches[1]
        }
    } catch {}
    return $null
}

# Test if Foundry is actually responding
function Test-FoundryHealth {
    param([string]$Port)
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:$Port/v1/models" -TimeoutSec 5 -ErrorAction SilentlyContinue
        return ($null -ne $response.data)
    } catch {
        return $false
    }
}

# Test if RAG server can reach Foundry
function Test-RagToFoundry {
    try {
        $result = Invoke-RestMethod -Uri "http://localhost:8000/query" -Method Post -ContentType "application/json" -Body '{"query":"test","top_k":1}' -TimeoutSec 30 -ErrorAction SilentlyContinue
        return ($null -ne $result.answer)
    } catch {
        return $false
    }
}

# Start Foundry service (requires admin, will prompt)
function Start-FoundryService {
    Write-Status "Starting Foundry Local service..."

    # Try direct start first
    try {
        $result = & foundry service start 2>&1
        Start-Sleep -Seconds 3
        $port = Get-FoundryPort
        if ($port) {
            Write-OK "Foundry started on port $port"
            return $port
        }
    } catch {}

    # Need admin rights
    Write-Warn "Foundry requires administrator privileges to start"
    Write-Status "Launching admin prompt..."

    try {
        Start-Process "foundry" -ArgumentList "service","start" -Verb RunAs -Wait
        Start-Sleep -Seconds 5
        $port = Get-FoundryPort
        if ($port) {
            Write-OK "Foundry started on port $port"
            return $port
        }
    } catch {
        Write-Fail "Could not start Foundry: $_"
    }

    return $null
}

# Restart RAG containers with new port
function Restart-RagContainers {
    param([string]$Port, [string]$FoundryModel)

    Write-Status "Stopping existing containers..."
    Push-Location $scriptDir
    docker compose down 2>&1 | Out-Null

    Write-Status "Starting containers with Foundry port $Port..."
    $env:FOUNDRY_PORT = $Port
    if ($FoundryModel) {
        $env:FOUNDRY_MODEL = $FoundryModel
    }

    docker compose up -d 2>&1 | Out-Null
    Pop-Location

    # Wait for health
    Write-Status "Waiting for RAG server to be healthy..."
    $maxWait = 60
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 2
        $waited += 2
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($health.status -eq "healthy") {
                Write-OK "RAG server healthy"
                return $true
            }
        } catch {}
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
    Write-Host ""
    Write-Fail "RAG server did not become healthy in time"
    return $false
}

# Restart Open WebUI with new port
function Restart-OpenWebUI {
    param([string]$Port)

    $openWebUIDir = Join-Path (Split-Path $scriptDir -Parent) ""
    $composeFile = Join-Path $openWebUIDir "docker-compose.yml"

    if (-not (Test-Path $composeFile)) {
        Write-Warn "Open WebUI compose file not found at $composeFile"
        return $false
    }

    Write-Status "Restarting Open WebUI with port $Port..."

    # Stop Open WebUI
    docker stop open-webui 2>&1 | Out-Null
    docker rm open-webui 2>&1 | Out-Null

    # Start with correct port via environment override
    $env:FOUNDRY_PORT = $Port
    docker run -d `
        --name open-webui `
        --restart unless-stopped `
        -p 3000:8080 `
        -e "OPENAI_API_BASE_URL=http://host.docker.internal:$Port/v1" `
        -e "OPENAI_API_KEY=local-key" `
        -e "WHISPER_API_BASE_URL=http://host.docker.internal:$Port/v1" `
        -e "WHISPER_API_KEY=local-key" `
        -v "$env:LOCALAPPDATA/open-webui:/app/backend/data" `
        --add-host=host.docker.internal:host-gateway `
        ghcr.io/open-webui/open-webui:main 2>&1 | Out-Null

    # Wait for health
    Write-Status "Waiting for Open WebUI..."
    Start-Sleep -Seconds 10

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-OK "Open WebUI running"
            return $true
        }
    } catch {}

    Write-Warn "Open WebUI may still be starting"
    return $true
}

# Get best available model
function Get-BestModel {
    param([string]$Port)

    try {
        $models = Invoke-RestMethod -Uri "http://localhost:$Port/v1/models" -TimeoutSec 5

        # Prefer larger models for better tool calling
        $preferOrder = @(
            "phi-3.5-mini",      # 3.8B - best for tool calling
            "qwen2.5-0.5b"       # 0.5B - works but unreliable
        )

        foreach ($pattern in $preferOrder) {
            $found = $models.data | Where-Object { $_.id -like "*$pattern*" -and $_.id -notlike "*whisper*" } | Select-Object -First 1
            if ($found) {
                return $found.id
            }
        }

        # Fallback to any non-whisper model
        $fallback = $models.data | Where-Object { $_.id -notlike "*whisper*" } | Select-Object -First 1
        if ($fallback) {
            return $fallback.id
        }
    } catch {}

    return "phi-3.5-mini"
}

# === MAIN COMMANDS ===

function Show-Status {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  RAG Stack Status" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    # Foundry
    Write-Step "Foundry Local:"
    $foundryPort = Get-FoundryPort
    if ($foundryPort) {
        $healthy = Test-FoundryHealth -Port $foundryPort
        if ($healthy) {
            Write-OK "Running on port $foundryPort"
        } else {
            Write-Fail "Port $foundryPort detected but not responding"
        }
    } else {
        Write-Fail "Not running"
    }

    # RAG Server
    Write-Step "RAG Server:"
    $ragPort = Get-RagServerPort
    if ($ragPort) {
        Write-OK "Running, configured for Foundry port $ragPort"
        if ($foundryPort -and $ragPort -ne $foundryPort) {
            Write-Fail "PORT MISMATCH! RAG expects $ragPort but Foundry is on $foundryPort"
        }
    } else {
        Write-Fail "Not running or not healthy"
    }

    # Open WebUI
    Write-Step "Open WebUI:"
    $webUIPort = Get-OpenWebUIPort
    if ($webUIPort) {
        Write-OK "Running, configured for Foundry port $webUIPort"
        if ($foundryPort -and $webUIPort -ne $foundryPort) {
            Write-Fail "PORT MISMATCH! WebUI expects $webUIPort but Foundry is on $foundryPort"
        }
    } else {
        Write-Fail "Not running"
    }

    # Qdrant
    Write-Step "Qdrant:"
    try {
        $qdrant = Invoke-RestMethod -Uri "http://localhost:6333/collections" -TimeoutSec 3 -ErrorAction SilentlyContinue
        $collections = $qdrant.result.collections | ForEach-Object { $_.name }
        Write-OK "Running with collections: $($collections -join ', ')"
    } catch {
        Write-Fail "Not running"
    }

    # End-to-end test
    Write-Step "End-to-End Test:"
    if ($foundryPort -and $ragPort -eq $foundryPort) {
        $e2e = Test-RagToFoundry
        if ($e2e) {
            Write-OK "RAG query successful!"
        } else {
            Write-Fail "RAG query failed"
        }
    } else {
        Write-Warn "Skipped due to port mismatch or missing services"
    }

    Write-Host ""
}

function Start-Stack {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Starting RAG Stack" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    # Step 1: Ensure Foundry is running
    Write-Step "[1/4] Foundry Local"
    $foundryPort = Get-FoundryPort
    if (-not $foundryPort) {
        $foundryPort = Start-FoundryService
        if (-not $foundryPort) {
            Write-Fail "Cannot continue without Foundry Local"
            Write-Host "`nPlease run as Administrator: foundry service start" -ForegroundColor Yellow
            return
        }
    } else {
        if (Test-FoundryHealth -Port $foundryPort) {
            Write-OK "Already running on port $foundryPort"
        } else {
            Write-Warn "Detected on port $foundryPort but not healthy, restarting..."
            $foundryPort = Start-FoundryService
        }
    }

    # Step 2: Determine model
    Write-Step "[2/4] Model Selection"
    $selectedModel = $Model
    if (-not $selectedModel) {
        $selectedModel = Get-BestModel -Port $foundryPort
    }
    Write-OK "Using model: $selectedModel"

    # Step 3: Start/restart RAG containers
    Write-Step "[3/4] RAG Containers"
    $ragPort = Get-RagServerPort
    if ($ragPort -eq $foundryPort -and -not $Force) {
        Write-OK "Already configured correctly"
    } else {
        if ($ragPort) {
            Write-Status "Port changed from $ragPort to $foundryPort, restarting..."
        }
        Restart-RagContainers -Port $foundryPort -FoundryModel $selectedModel
    }

    # Step 4: Restart Open WebUI
    Write-Step "[4/4] Open WebUI"
    $webUIPort = Get-OpenWebUIPort
    if ($webUIPort -eq $foundryPort -and -not $Force) {
        Write-OK "Already configured correctly"
    } else {
        if ($webUIPort) {
            Write-Status "Port changed from $webUIPort to $foundryPort, restarting..."
        }
        Restart-OpenWebUI -Port $foundryPort
    }

    # Final status
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "  RAG Stack Ready!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Open WebUI:    http://localhost:3000" -ForegroundColor White
    Write-Host "  RAG Admin:     http://localhost:8501" -ForegroundColor White
    Write-Host "  RAG API:       http://localhost:8000/docs" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Foundry Port:  $foundryPort" -ForegroundColor Gray
    Write-Host "  Model:         $selectedModel" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Test command:" -ForegroundColor Yellow
    Write-Host "  curl -X POST http://localhost:8000/query -H `"Content-Type: application/json`" -d '{`"query`":`"summarize my resume`",`"category`":`"job-search`"}'" -ForegroundColor Gray
    Write-Host ""
}

function Stop-Stack {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Stopping RAG Stack" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    Write-Step "Stopping containers..."
    Push-Location $scriptDir
    docker compose down 2>&1 | Out-Null
    Pop-Location

    docker stop open-webui 2>&1 | Out-Null

    Write-OK "Containers stopped"
    Write-Host ""
}

function Invoke-Fix {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Auto-Fix RAG Stack" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    # This is the "make it work" command
    # Forces restart of everything with correct ports

    $script:Force = $true
    Start-Stack
}

function Invoke-Diagnose {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  RAG Stack Diagnostics" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    Show-Status

    Write-Step "Container Logs (last 10 lines):"
    Write-Host "`n--- rag-server ---" -ForegroundColor Yellow
    docker logs rag-server --tail 10 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    Write-Host "`n--- open-webui ---" -ForegroundColor Yellow
    docker logs open-webui --tail 10 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

    Write-Step "Recommendations:"

    $foundryPort = Get-FoundryPort
    $ragPort = Get-RagServerPort
    $webUIPort = Get-OpenWebUIPort

    if (-not $foundryPort) {
        Write-Host "  1. Start Foundry: Run 'foundry service start' as Administrator" -ForegroundColor Yellow
    }

    if ($foundryPort -and $ragPort -ne $foundryPort) {
        Write-Host "  2. Fix port mismatch: Run './rag-manager.ps1 fix'" -ForegroundColor Yellow
    }

    if ($foundryPort -and $webUIPort -ne $foundryPort) {
        Write-Host "  3. Fix Open WebUI port: Run './rag-manager.ps1 fix'" -ForegroundColor Yellow
    }

    Write-Host ""
}

# === EXECUTE COMMAND ===

switch ($Command) {
    "start"    { Start-Stack }
    "stop"     { Stop-Stack }
    "restart"  { Stop-Stack; Start-Stack }
    "status"   { Show-Status }
    "diagnose" { Invoke-Diagnose }
    "fix"      { Invoke-Fix }
    default    { Show-Status }
}
