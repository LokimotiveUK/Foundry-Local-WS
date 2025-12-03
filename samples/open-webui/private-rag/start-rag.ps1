# Start Private RAG Stack
# Launches Qdrant + RAG Server alongside Open WebUI

param(
    [switch]$IngestOnly,
    [switch]$SkipQdrant
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Private RAG Stack for Healthcare & Finance" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker is running
Write-Host "[1/5] Checking Docker..." -ForegroundColor Yellow
try {
    docker info 2>&1 | Out-Null
    Write-Host "  Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Start Qdrant if not running
if (-not $SkipQdrant) {
    Write-Host ""
    Write-Host "[2/5] Starting Qdrant vector database..." -ForegroundColor Yellow

    $qdrantRunning = docker ps --filter "name=qdrant" --format "{{.Names}}" 2>$null
    if ($qdrantRunning -eq "qdrant") {
        Write-Host "  Qdrant already running" -ForegroundColor Green
    } else {
        # Remove old container if exists
        docker rm -f qdrant 2>$null | Out-Null

        # Start Qdrant with persistent storage
        $localAppData = $env:LOCALAPPDATA
        docker run -d --name qdrant `
            -p 6333:6333 -p 6334:6334 `
            -v "${localAppData}\qdrant:/qdrant/storage" `
            qdrant/qdrant

        Write-Host "  Qdrant started on port 6333" -ForegroundColor Green

        # Wait for Qdrant to be ready
        Write-Host "  Waiting for Qdrant to initialize..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
} else {
    Write-Host ""
    Write-Host "[2/5] Skipping Qdrant (--SkipQdrant flag)" -ForegroundColor Gray
}

# Check for Python dependencies
Write-Host ""
Write-Host "[3/5] Checking Python dependencies..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

try {
    python -c "import qdrant_client, sentence_transformers, fastapi" 2>&1 | Out-Null
    Write-Host "  Dependencies installed" -ForegroundColor Green
} catch {
    Write-Host "  Installing dependencies..." -ForegroundColor Gray
    pip install -r "$scriptDir\requirements.txt"
    Write-Host "  Dependencies installed" -ForegroundColor Green
}

# Check if documents exist and ingest if needed
Write-Host ""
Write-Host "[4/5] Checking documents..." -ForegroundColor Yellow

$healthcareDir = Join-Path $scriptDir "documents\healthcare"
$financeDir = Join-Path $scriptDir "documents\finance"

$healthcareDocs = Get-ChildItem -Path $healthcareDir -File -ErrorAction SilentlyContinue
$financeDocs = Get-ChildItem -Path $financeDir -File -ErrorAction SilentlyContinue

$totalDocs = 0
if ($healthcareDocs) { $totalDocs += $healthcareDocs.Count }
if ($financeDocs) { $totalDocs += $financeDocs.Count }

if ($totalDocs -eq 0) {
    Write-Host "  No documents found. Add files to:" -ForegroundColor Yellow
    Write-Host "    - $healthcareDir" -ForegroundColor Gray
    Write-Host "    - $financeDir" -ForegroundColor Gray
} else {
    Write-Host "  Found $totalDocs document(s)" -ForegroundColor Green

    # Check if we need to ingest
    $shouldIngest = $IngestOnly
    if (-not $shouldIngest) {
        $response = Read-Host "  Do you want to (re)ingest documents? [y/N]"
        $shouldIngest = $response -eq "y" -or $response -eq "Y"
    }

    if ($shouldIngest) {
        Write-Host "  Running document ingestion..." -ForegroundColor Gray
        Push-Location $scriptDir
        python ingest.py
        Pop-Location
    }
}

if ($IngestOnly) {
    Write-Host ""
    Write-Host "Ingestion complete. Exiting (--IngestOnly flag)" -ForegroundColor Green
    exit 0
}

# Start RAG server
Write-Host ""
Write-Host "[5/5] Starting RAG server..." -ForegroundColor Yellow
Write-Host "  Server will run at http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  RAG Stack Ready!" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Qdrant:      http://localhost:6333" -ForegroundColor White
Write-Host "  RAG Server:  http://localhost:8000" -ForegroundColor White
Write-Host "  Open WebUI:  http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  API Endpoints:" -ForegroundColor Gray
Write-Host "    POST /query   - Ask questions about your documents" -ForegroundColor Gray
Write-Host "    POST /search  - Semantic search (no LLM)" -ForegroundColor Gray
Write-Host "    GET  /health  - Health check" -ForegroundColor Gray
Write-Host "    GET  /stats   - Collection statistics" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

Push-Location $scriptDir
python rag_server.py
Pop-Location
