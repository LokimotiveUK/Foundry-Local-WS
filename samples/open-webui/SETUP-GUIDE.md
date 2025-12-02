# Local AI Stack Setup Guide

This guide will help you set up a **completely offline** AI chat system using Foundry Local and Open WebUI. Everything runs locally - no internet connection required after initial setup.

## What You Have Now

✅ **Open WebUI** - Running at `http://localhost:3000` (web interface for chatting)
✅ **Docker Image** - Cached locally (`ghcr.io/open-webui/open-webui:main`)
⏳ **Foundry Local** - Needs to be started (AI model runtime)

## Quick Start

### Option 1: Use the Setup Script

```powershell
cd samples\open-webui
.\setup.ps1
```

Then manually start Foundry (requires admin rights):
```powershell
foundry service start
foundry model load phi-3.5-mini
foundry model load qwen2.5-0.5b
```

### Option 2: Manual Setup

If you prefer to do everything manually or the script doesn't work:

#### Step 1: Start Foundry Local Service

Open PowerShell **as Administrator** and run:

```powershell
foundry service start
```

Verify it's running:
```powershell
foundry server status
```

You should see output like:
```
✅ Model management service is running
📡 Server endpoint: http://localhost:5273/v1
```

#### Step 2: Load AI Models

Load the chat models (this downloads them if not already cached):

```powershell
foundry model load phi-3.5-mini
foundry model load qwen2.5-0.5b
```

These models will be optimized for your NPU hardware automatically.

Optional - Load Whisper for speech-to-text:
```powershell
foundry model load whisper-small
```

Verify models are loaded:
```powershell
foundry model ls
```

#### Step 3: Launch Open WebUI (Already Done!)

The container is already running at `http://localhost:3000`

To verify:
```powershell
docker ps --filter "name=open-webui"
```

To restart if needed:
```powershell
docker restart open-webui
```

## Configure Open WebUI to Use Local Models

1. **Open your browser** and go to `http://localhost:3000`

2. **Create admin account** (first signup only):
   - Username: your choice
   - Password: your choice
   - This data is stored locally in `%LOCALAPPDATA%\open-webui`

3. **Add models to Open WebUI**:
   - Click your profile icon → **Admin Settings**
   - Go to **Settings** → **Connections**
   - Verify "OpenAI API" section shows:
     - API Base URL: `http://host.docker.internal:5273/v1`
     - API Key: `local-key`

4. **Get model IDs from Foundry**:

   Open PowerShell and run:
   ```powershell
   foundry model ls --details
   ```

   Example output:
   ```
   phi-3.5-mini-instruct-generic-npu
   qwen2.5-0.5b-instruct-generic-npu
   ```

5. **Add models in Open WebUI**:
   - In Admin Settings, go to **Models**
   - Click **+ Add Model**
   - For each model:
     - **Model Name**: `phi-3.5-mini` (display name)
     - **Model ID**: `phi-3.5-mini-instruct-generic-npu` (from foundry ls)
     - Click **Save**
   - Repeat for `qwen2.5-0.5b`

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
foundry server status
foundry model ls
```
Should show service running and models loaded.

### Test 3: Test API Directly
```powershell
curl http://localhost:5273/v1/models
```
Should return JSON with available models.

### Test 4: Check Container Connectivity
```powershell
docker exec open-webui curl -s http://host.docker.internal:5273/v1/models
```
Should return model list (proves Docker can reach Foundry).

## Troubleshooting

### Open WebUI shows "No models available"

**Solution**: Make sure models are added in Admin Settings using the exact Model IDs from `foundry model ls --details`.

### "Connection refused" errors

**Problem**: Foundry Local service not running.

**Solution**:
```powershell
foundry service start
foundry server status
```

### Models not showing in Foundry

**Problem**: Models not loaded into memory.

**Solution**:
```powershell
foundry model load phi-3.5-mini
foundry model ls
```

### Docker container not starting

**Problem**: Port conflict or Docker not running.

**Solution**:
```powershell
# Check what's using port 3000
netstat -ano | findstr :3000

# Stop and remove container
docker stop open-webui
docker rm open-webui

# Restart setup
.\setup.ps1
```

### "Access denied" when starting Foundry service

**Problem**: Need administrator rights.

**Solution**: Open PowerShell as Administrator, then run:
```powershell
foundry service start
```

## Stopping Everything

### Stop Open WebUI only:
```powershell
docker stop open-webui
```

### Stop everything:
```powershell
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

1. ✅ Disconnect from internet
2. ✅ Start Foundry Local: `foundry service start`
3. ✅ Load models: `foundry model load phi-3.5-mini`
4. ✅ Start Open WebUI: `docker start open-webui`
5. ✅ Browse to `http://localhost:3000`
6. ✅ Chat completely offline!

All processing happens on your local NPU - no data leaves your machine.

## Advanced: Adding Whisper (Speech-to-Text)

If you loaded the Whisper model and want to enable voice input:

1. Stop the container:
   ```powershell
   docker stop open-webui
   docker rm open-webui
   ```

2. Modify the docker run command in `setup.ps1` to include:
   ```powershell
   -e WHISPER_API_BASE_URL=http://host.docker.internal:5273/v1 `
   -e WHISPER_API_KEY=local-key `
   ```

3. Restart container with new env vars

4. The microphone icon in Open WebUI will now transcribe locally!

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
- Monitor model cache status: `foundry model ls --details`

---

**Need help?** Check the main [README.md](./README.md) or Foundry Local documentation.
