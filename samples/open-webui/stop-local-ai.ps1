# Stop Local AI Stack

Write-Host "Stopping Local AI Stack..." -ForegroundColor Yellow
Write-Host ""

# Stop Open WebUI container
Write-Host "[1/2] Stopping Open WebUI container..." -ForegroundColor Cyan
docker stop open-webui 2>$null
docker rm open-webui 2>$null
Write-Host "  ✓ Open WebUI stopped" -ForegroundColor Green

# Note about Foundry service
Write-Host ""
Write-Host "[2/2] Foundry Local service..." -ForegroundColor Cyan
Write-Host "  ℹ Foundry service continues running in background" -ForegroundColor Yellow
Write-Host "  To stop (requires admin): foundry service stop" -ForegroundColor Gray
Write-Host ""
Write-Host "✓ Local AI Stack stopped" -ForegroundColor Green
