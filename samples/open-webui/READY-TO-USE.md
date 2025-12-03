# Local AI System - Ready to Use

Your local AI system is configured and ready to use.

---

## Quick Start

The easiest way to start everything:

```powershell
cd samples\open-webui
.\start-local-ai.ps1
```

Then browse to: **http://localhost:3000**

---

## System Components

| Component | URL | Notes |
|-----------|-----|-------|
| **Open WebUI** | `http://localhost:3000` | Web chat interface |
| **Foundry Local** | Dynamic port | Check with `foundry service status` |

---

## Important: Dynamic Port

Foundry Local uses a **dynamic port** that changes each time the service restarts.

The startup scripts (`start-local-ai.ps1`, `start-local-ai-auto.ps1`) automatically detect and configure the correct port.

To check the current port manually:
```powershell
foundry service status
```

---

## Available Models

To see loaded models:
```powershell
foundry model list
```

Common models:
- **phi-3.5-mini** - Fast, NPU-optimized for general chat
- **qwen2.5-0.5b** - Lightweight, supports tool calling
- **whisper-small** - Speech-to-text (optional)

---

## Configure Open WebUI

1. Browse to `http://localhost:3000`
2. Create/login to your admin account
3. Models should appear automatically if Foundry is connected

If models don't appear:
- Re-run `.\start-local-ai.ps1` to refresh the connection
- Check Admin Settings > Connections to verify the API URL

---

## Quick Commands

```powershell
# Start everything (auto-detects port)
.\start-local-ai.ps1

# Start non-interactively
.\start-local-ai-auto.ps1

# Start with Whisper speech-to-text
.\start-local-ai-auto.ps1 -EnableWhisper

# Stop everything
.\stop-local-ai.ps1

# Check Foundry status and port
foundry service status

# Check loaded models
foundry model list
```

---

## Verify Setup

```powershell
# Check Open WebUI container
docker ps --filter "name=open-webui"

# Check Foundry service
foundry service status

# Test API (replace <PORT> with actual port)
curl http://localhost:<PORT>/v1/models
```

---

## Features

- **Offline AI Chat** - No internet needed after setup
- **NPU Acceleration** - Fast inference on Snapdragon X Elite/Plus
- **Multiple Models** - Switch between models in the UI
- **Speech-to-Text** - With Whisper enabled
- **Private & Secure** - All data stays on your device
- **Persistent History** - Chats saved locally

---

## Data Locations

| Data | Path |
|------|------|
| Open WebUI data | `%LOCALAPPDATA%\open-webui\` |
| Foundry models | `%LOCALAPPDATA%\foundry-local\` |

---

## Troubleshooting

**Models not appearing?**
```powershell
.\start-local-ai.ps1
```
This re-detects the Foundry port and restarts Open WebUI.

**Connection errors?**
Check that Foundry is running:
```powershell
foundry service status
```

**Need more help?**
See `SETUP-GUIDE.md` for detailed troubleshooting.

---

**Go to http://localhost:3000 and start chatting with your private, offline AI assistant!**
