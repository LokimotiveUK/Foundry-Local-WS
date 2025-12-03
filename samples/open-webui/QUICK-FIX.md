# Quick Fix Reference

This document tracks common issues and their fixes for the Open WebUI + Foundry Local integration.

---

## Fix 1: Signup Permission Error

**Issue**: Open WebUI showing "You do not have permission to access this resource" on the signup page.

**Cause**: Container was launched with `ENABLE_SIGNUP=false` before any admin account existed.

**Fix**: Restart container without the signup restriction, or use the startup scripts which handle this correctly.

---

## Fix 2: Models Not Appearing (Port Mismatch)

**Issue**: Open WebUI shows no models or "connection refused" errors.

**Cause**: Foundry Local uses a **dynamic port** that changes on each service restart. If Open WebUI was configured with an old port, it can't connect.

**Fix**: Use the startup script to automatically detect the correct port:

```powershell
.\start-local-ai.ps1
```

Or manually:
1. Check current port: `foundry service status`
2. Restart Open WebUI with new port:
```powershell
docker stop open-webui
docker rm open-webui
docker run -d --name open-webui --restart=unless-stopped `
  -p 3000:8080 `
  -e OPENAI_API_BASE_URL="http://host.docker.internal:<PORT>/v1" `
  -e OPENAI_API_KEY="local-key" `
  -v "$Env:LOCALAPPDATA\open-webui:/app/backend/data" `
  ghcr.io/open-webui/open-webui:main
```

---

## Fix 3: "Backend Required" Error

**Issue**: Browser shows "Open WebUI Backend Required" message.

**Cause**: Browser cached an old frontend-only version.

**Fix**:
1. Clear browser cache or use incognito/private window
2. Access `http://localhost:3000` (not https)
3. Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

---

## Fix 4: Foundry Service Access Denied

**Issue**: `foundry service start` returns "Access denied".

**Cause**: Need administrator privileges.

**Fix**: Run PowerShell as Administrator, then:
```powershell
foundry service start
```

---

## Fix 5: Wrong Foundry Commands

**Issue**: Commands like `foundry server status` or `foundry model load` don't work.

**Cause**: Foundry CLI commands have changed.

**Correct Commands**:
```powershell
# Check service status (shows port)
foundry service status

# Load/run a model
foundry model run phi-3.5-mini

# List models
foundry model list
```

---

## Prevention: Use Automated Scripts

The startup scripts handle all these issues automatically:

```powershell
# Interactive (recommended)
.\start-local-ai.ps1

# Non-interactive
.\start-local-ai-auto.ps1

# With Whisper enabled
.\start-local-ai-auto.ps1 -EnableWhisper
```

These scripts:
- Detect the dynamic Foundry port
- Configure Open WebUI with the correct endpoint
- Handle container lifecycle properly
- Load required models

---

## Current Status

All known issues have fixes documented above. The startup scripts now automatically detect the dynamic Foundry port, which was the main source of connection problems.
