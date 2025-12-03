# Local AI Stack - Current Status

**Location**: `C:\GitHub\Foundry-Local\Foundry-Local-WS\samples\open-webui\`

---

## System Components

| Component | Status | Notes |
|-----------|--------|-------|
| **Open WebUI** | Container | `http://localhost:3000` |
| **Docker Image** | Cached | `ghcr.io/open-webui/open-webui:main` |
| **Foundry Local** | Service | Dynamic port (check with `foundry service status`) |

---

## Important: Dynamic Port

Foundry Local uses a **dynamic port** that changes each time the service restarts. Always check the current port:

```powershell
foundry service status
```

Example output: `http://127.0.0.1:57537/openai/status` - the port is **57537**.

The startup scripts (`start-local-ai.ps1`, `start-local-ai-auto.ps1`) automatically detect and configure the correct port.

---

## Files in this Directory

| File | Purpose |
|------|---------|
| `README.md` | Main documentation with Quick Start |
| `SETUP-GUIDE.md` | Comprehensive step-by-step setup guide |
| `STATUS.md` | This file - quick reference |
| `docker-compose.yml` | Docker Compose configuration (requires manual port update) |
| `start-local-ai.ps1` | **Interactive startup script (RECOMMENDED)** |
| `start-local-ai-auto.ps1` | Non-interactive startup script |
| `stop-local-ai.ps1` | Shutdown script |
| `setup.ps1` | Simple setup script |

---

## Quick Start

The easiest way to start everything:

```powershell
cd samples\open-webui
.\start-local-ai.ps1
```

This will:
1. Start/verify Foundry service
2. Detect the dynamic port automatically
3. Load AI models
4. Launch Open WebUI with correct configuration
5. Optionally enable Whisper for speech-to-text

Then browse to: `http://localhost:3000`

---

## Quick Commands

### Check Status
```powershell
# Check Foundry service and port
foundry service status

# Check loaded models
foundry model list

# Check Open WebUI container
docker ps --filter "name=open-webui"
```

### Restart Open WebUI
```powershell
.\start-local-ai.ps1
# Or just restart container (keeps existing config):
docker restart open-webui
```

### View Logs
```powershell
# Open WebUI logs
docker logs open-webui --tail 50 -f
```

### Stop Everything
```powershell
.\stop-local-ai.ps1
```

### Start Everything from Scratch
```powershell
cd samples\open-webui
.\start-local-ai.ps1
```

---

## Data Locations

| Data | Path |
|------|------|
| Open WebUI database | `%LOCALAPPDATA%\open-webui\webui.db` |
| Chat history | `%LOCALAPPDATA%\open-webui\` |
| Foundry models cache | `%LOCALAPPDATA%\foundry-local\` |

---

## Features Available

Once fully set up, you'll have:

- **Offline AI Chat** - No internet required
- **NPU Acceleration** - Uses Snapdragon X Elite/Plus NPU
- **Multiple Models** - Switch between loaded models
- **Web Interface** - ChatGPT-like experience via Open WebUI
- **Privacy First** - All data stays on your device
- **Speech-to-Text** - Available with `-EnableWhisper` flag
- **Custom Personas** - Configure in Open WebUI settings

---

## Troubleshooting

### Models not appearing?
The Foundry port may have changed. Re-run:
```powershell
.\start-local-ai.ps1
```

### Need to check the current port?
```powershell
foundry service status
```

### Container not connecting to Foundry?
Port mismatch - restart with the script to auto-detect:
```powershell
.\start-local-ai.ps1
```

---

## Documentation

- **Quick Start**: See `README.md`
- **Detailed Setup**: See `SETUP-GUIDE.md`
- **Troubleshooting**: See `SETUP-GUIDE.md` -> Troubleshooting section
