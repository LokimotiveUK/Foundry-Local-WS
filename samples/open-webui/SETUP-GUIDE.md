# Local AI Stack Setup Guide

This guide will help you set up a **completely offline** AI chat system using Foundry Local and Open WebUI. Everything runs locally - no internet connection required after initial setup.

## Important: Dynamic Port

Foundry Local uses a **dynamic port** that changes each time the service restarts. The startup scripts automatically detect this port, but if you're setting up manually, you'll need to check the current port:

```powershell
foundry service status
```

This will show output like: `http://127.0.0.1:57537/openai/status` - note the port number (57537 in this example).

## Quick Start

### Option 1: Use the Automated Script (Recommended)

```powershell
cd samples\open-webui
.\start-local-ai.ps1
```

This script will:
- Start Foundry Local service
- Automatically detect the Foundry port
- Load AI models
- Launch Open WebUI with the correct port configuration

For non-interactive automation:
```powershell
.\start-local-ai-auto.ps1
# Or with Whisper:
.\start-local-ai-auto.ps1 -EnableWhisper
```

### Option 2: Manual Setup

If you prefer to do everything manually:

#### Step 1: Start Foundry Local Service

Open PowerShell **as Administrator** and run:

```powershell
foundry service start
```

Check the port:
```powershell
foundry service status
```

Note the port number from the output (e.g., `http://127.0.0.1:57537`).

#### Step 2: Load AI Models

Load the chat models (this downloads them if not already cached):

```powershell
foundry model run phi-3.5-mini
foundry model run qwen2.5-0.5b
```

These models will be optimized for your NPU hardware automatically.

Optional - Load Whisper for speech-to-text:
```powershell
foundry model run whisper-small
```

Verify models are loaded:
```powershell
foundry model list
```

#### Step 3: Launch Open WebUI

Replace `<PORT>` with the port from Step 1:

```powershell
docker run -d --name open-webui --restart=unless-stopped `
  -p 3000:8080 `
  -e OPENAI_API_BASE_URL="http://host.docker.internal:<PORT>/v1" `
  -e OPENAI_API_KEY="local-key" `
  -v "$Env:LOCALAPPDATA\open-webui:/app/backend/data" `
  ghcr.io/open-webui/open-webui:main
```

To verify:
```powershell
docker ps --filter "name=open-webui"
```

## Configure Open WebUI to Use Local Models

1. **Open your browser** and go to `http://localhost:3000`

2. **Create admin account** (first signup only):
   - Username: your choice
   - Password: your choice
   - This data is stored locally in `%LOCALAPPDATA%\open-webui`

3. **Verify connection settings**:
   - Click your profile icon -> **Admin Settings**
   - Go to **Settings** -> **Connections**
   - Verify "OpenAI API" section shows:
     - API Base URL: `http://host.docker.internal:<PORT>/v1` (with your actual port)
     - API Key: `local-key`

4. **Get model IDs from Foundry**:

   Open PowerShell and run:
   ```powershell
   foundry model list
   ```

5. **Add models in Open WebUI**:
   - In Admin Settings, go to **Models**
   - Click **+ Add Model**
   - For each model:
     - **Model Name**: `phi-3.5-mini` (display name)
     - **Model ID**: (use the ID from foundry model list)
     - Click **Save**
   - Repeat for other models

6. **Start chatting!**:
   - Go back to main chat interface
   - Select a model from the dropdown
   - Type a message and watch it stream from your local NPU!

## Verify Everything is Working

### Test 1: Check Container
```powershell
docker ps --filter "name=open-webui"
```
Should show `Up` status.

### Test 2: Check Foundry
```powershell
foundry service status
foundry model list
```
Should show service running and models loaded.

### Test 3: Test API Directly
Replace `<PORT>` with your actual port:
```powershell
curl http://localhost:<PORT>/v1/models
```
Should return JSON with available models.

### Test 4: Check Container Connectivity
Replace `<PORT>` with your actual port:
```powershell
docker exec open-webui curl -s http://host.docker.internal:<PORT>/v1/models
```
Should return model list (proves Docker can reach Foundry).

## Troubleshooting

### Open WebUI shows "No models available"

**Cause**: Port mismatch between Open WebUI and Foundry.

**Solution**:
1. Check the current Foundry port: `foundry service status`
2. Restart Open WebUI with the correct port using `.\start-local-ai.ps1`

### "Connection refused" errors

**Cause**: Foundry Local service not running, or wrong port.

**Solution**:
```powershell
foundry service status
# If not running:
foundry service start
```

### Models not showing in Foundry

**Cause**: Models not loaded into memory.

**Solution**:
```powershell
foundry model run phi-3.5-mini
foundry model list
```

### Docker container not starting

**Cause**: Port conflict or Docker not running.

**Solution**:
```powershell
# Check what's using port 3000
netstat -ano | findstr :3000

# Stop and remove container
docker stop open-webui
docker rm open-webui

# Restart with the automated script
.\start-local-ai.ps1
```

### "Access denied" when starting Foundry service

**Cause**: Need administrator rights.

**Solution**: Open PowerShell as Administrator, then run:
```powershell
foundry service start
```

### Port changed after Foundry restart

**Cause**: Foundry uses dynamic ports.

**Solution**: Re-run the startup script to detect the new port:
```powershell
.\start-local-ai.ps1
```

## Stopping Everything

### Stop Open WebUI only:
```powershell
docker stop open-webui
```

### Stop everything:
```powershell
.\stop-local-ai.ps1
# Or manually:
docker stop open-webui
foundry service stop  # Requires admin rights
```

## Data Storage Locations

| Component | Location |
|-----------|----------|
| Open WebUI data | `%LOCALAPPDATA%\open-webui\` |
| Foundry models | `%LOCALAPPDATA%\foundry-local\` |
| Docker image cache | Docker Desktop managed |

## Going Completely Offline

Once everything is set up and models are cached:

1. Disconnect from internet
2. Start Foundry Local: `foundry service start`
3. Load models: `foundry model run phi-3.5-mini`
4. Run the startup script: `.\start-local-ai.ps1`
5. Browse to `http://localhost:3000`
6. Chat completely offline!

All processing happens on your local NPU - no data leaves your machine.

## Advanced: Adding Whisper (Speech-to-Text)

Use the startup script with the Whisper flag:

```powershell
.\start-local-ai.ps1
# Answer 'y' when prompted for Whisper

# Or for non-interactive:
.\start-local-ai-auto.ps1 -EnableWhisper
```

The microphone icon in Open WebUI will now transcribe locally!

## System Requirements

- Windows 11 with Snapdragon X Elite/Plus (NPU-optimized)
- Docker Desktop installed and running
- Foundry Local installed (`winget install Microsoft.FoundryLocal`)
- ~10GB disk space for models
- ~4GB RAM for models in memory

## Performance Tips

- Keep models loaded in memory for instant responses
- Use NPU-optimized variants (automatic via Foundry)
- Close other NPU-heavy applications for best performance
- Use the automated scripts to ensure correct port configuration

---

**Need help?** Check the main [README.md](./README.md) or Foundry Local documentation.
