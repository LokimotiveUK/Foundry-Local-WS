Write-Host "Setting up Local AI Stack..." -ForegroundColor Cyan

# Launch Open WebUI
Write-Host "Launching Open WebUI container..." -ForegroundColor Yellow
docker stop open-webui 2>$null
docker rm open-webui 2>$null

$dataPath = "$env:LOCALAPPDATA\open-webui"
New-Item -ItemType Directory -Path $dataPath -Force -ErrorAction SilentlyContinue | Out-Null

docker run -d `
  --name open-webui `
  --restart unless-stopped `
  -p 3000:8080 `
  -e OPENAI_API_BASE_URL=http://host.docker.internal:52089/v1 `
  -e OPENAI_API_KEY=local-key `
  -v "${dataPath}:/app/backend/data" `
  ghcr.io/open-webui/open-webui:main

Start-Sleep -Seconds 8

$status = docker ps --filter "name=open-webui" --format "table {{.Status}}"
if ($status -match "Up") {
    Write-Host ""
    Write-Host "SUCCESS! Open WebUI is running at http://localhost:3000" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: Start Foundry Local service and load models:" -ForegroundColor Yellow
    Write-Host "  foundry service start" -ForegroundColor White
    Write-Host "  foundry model load phi-3.5-mini" -ForegroundColor White
    Write-Host "  foundry model load qwen2.5-0.5b" -ForegroundColor White
} else {
    Write-Host "Container may still be starting..." -ForegroundColor Yellow
    docker ps -a --filter "name=open-webui"
}
