# start-rag.ps1
# Starts the Private RAG stack with auto-detected Foundry port
#
# Usage:
#   ./start-rag.ps1              # Start all services
#   ./start-rag.ps1 -Rebuild     # Rebuild and start
#   ./start-rag.ps1 -Stop        # Stop all services
#   ./start-rag.ps1 -Restart     # Restart with fresh Foundry port detection

param(
    [switch]$Rebuild,
    [switch]$Stop,
    [switch]$Restart,
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Private RAG Stack Manager" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Stop services if requested
if ($Stop) {
    Write-Host "`nStopping RAG services..." -ForegroundColor Yellow
    docker compose down
    Write-Host "Done!" -ForegroundColor Green
    exit 0
}

# Restart = stop then continue
if ($Restart) {
    Write-Host "`nRestarting RAG services..." -ForegroundColor Yellow
    docker compose down
}

# Check Docker is running
Write-Host "`n[1/4] Checking Docker..." -ForegroundColor Yellow
try {
    docker info 2>&1 | Out-Null
    Write-Host "  Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if Foundry is running and get the port
Write-Host "`n[2/4] Detecting Foundry Local..." -ForegroundColor Yellow
$foundryStatus = & foundry service status 2>&1 | Out-String

if ($foundryStatus -match "not running") {
    Write-Host "  Foundry Local is not running. Starting it..." -ForegroundColor Yellow
    & foundry service start
    Start-Sleep -Seconds 3
    $foundryStatus = & foundry service status 2>&1 | Out-String
}

# Extract port from status - look for port number after localhost or 127.0.0.1
$foundryPort = "5273"  # default
if ($foundryStatus -match "127\.0\.0\.1:(\d+)" -or $foundryStatus -match "localhost:(\d+)") {
    $foundryPort = $Matches[1]
    Write-Host "  Foundry Local running on port: $foundryPort" -ForegroundColor Green
} elseif ($foundryStatus -match ":(\d{5})") {
    # Fallback: look for any 5-digit port number (Foundry uses high ports like 51413)
    $foundryPort = $Matches[1]
    Write-Host "  Foundry Local running on port: $foundryPort" -ForegroundColor Green
} else {
    Write-Host "  Could not detect Foundry port from status output." -ForegroundColor Yellow
    Write-Host "  Status: $foundryStatus" -ForegroundColor Gray
    Write-Host "  Using default: $foundryPort" -ForegroundColor Yellow
}

# Set environment variable for docker compose
$env:FOUNDRY_PORT = $foundryPort

# Auto-detect best available model if not specified
Write-Host "`n[3/4] Detecting available models..." -ForegroundColor Yellow
if ($Model -eq "") {
    try {
        $modelsResponse = Invoke-RestMethod -Uri "http://localhost:$foundryPort/v1/models" -Method Get -TimeoutSec 5 -ErrorAction SilentlyContinue

        # Prefer models in this order: qwen2.5 (has tool calling), phi-3.5
        $preferredPatterns = @(
            "qwen2.5-0.5b-instruct",
            "qwen2.5-coder",
            "phi-3.5-mini"
        )

        foreach ($pattern in $preferredPatterns) {
            $found = $modelsResponse.data | Where-Object { $_.id -like "*$pattern*" } | Select-Object -First 1
            if ($found) {
                $Model = $found.id
                $toolSupport = if ($found.toolCalling) { "(supports tool calling)" } else { "" }
                Write-Host "  Selected model: $Model $toolSupport" -ForegroundColor Green
                break
            }
        }

        if ($Model -eq "") {
            # Fall back to first available model that's not whisper
            $available = $modelsResponse.data | Where-Object { $_.id -notlike "*whisper*" } | Select-Object -First 1
            if ($available) {
                $Model = $available.id
                Write-Host "  Using available model: $Model" -ForegroundColor Yellow
            }
        }

        # List all available models
        Write-Host "  Available models:" -ForegroundColor Gray
        foreach ($m in $modelsResponse.data) {
            $marker = if ($m.id -eq $Model) { " <--" } else { "" }
            $tool = if ($m.toolCalling) { " [tools]" } else { "" }
            Write-Host "    - $($m.id)$tool$marker" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  Could not query models API: $_" -ForegroundColor Yellow
        $Model = "phi-3.5-mini"
        Write-Host "  Using default model: $Model" -ForegroundColor Yellow
    }
}

if ($Model -ne "") {
    $env:FOUNDRY_MODEL = $Model
}

# Start the stack
Write-Host "`n[4/4] Starting RAG services..." -ForegroundColor Yellow
Write-Host "  Foundry endpoint: http://host.docker.internal:$foundryPort/v1" -ForegroundColor Gray
Write-Host "  Model: $Model" -ForegroundColor Gray

if ($Rebuild) {
    docker compose up -d --build
} else {
    docker compose up -d
}

# Wait for services to be healthy
Write-Host "`nWaiting for services to initialize..." -ForegroundColor Yellow
$maxWait = 60
$waited = 0
$healthy = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    $waited += 2

    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($health.status -eq "healthy") {
            $healthy = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline -ForegroundColor Gray
    }
}

Write-Host ""

if ($healthy) {
    Write-Host "`n================================================" -ForegroundColor Green
    Write-Host "  RAG Stack Ready!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
} else {
    Write-Host "`nWarning: Services may still be starting." -ForegroundColor Yellow
    Write-Host "Check logs with: docker logs rag-server" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  RAG Admin UI:     http://localhost:8501" -ForegroundColor Cyan
Write-Host "  RAG API:          http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Qdrant Dashboard: http://localhost:6333/dashboard" -ForegroundColor Cyan
Write-Host "  Open WebUI:       http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Foundry Port: $foundryPort" -ForegroundColor Gray
Write-Host "  Model: $Model" -ForegroundColor Gray
Write-Host ""
Write-Host "To test the RAG API:" -ForegroundColor Yellow
Write-Host '  curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d "{\"query\": \"summarize my resume\", \"category\": \"job-search\"}"' -ForegroundColor Gray
Write-Host ""
Write-Host "To restart after Foundry port changes:" -ForegroundColor Yellow
Write-Host "  ./start-rag.ps1 -Restart" -ForegroundColor Gray
