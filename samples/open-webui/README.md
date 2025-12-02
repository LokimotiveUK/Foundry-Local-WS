# Sample: Open WebUI + Foundry Local

This sample shows how to point [Open WebUI](https://github.com/open-webui/open-webui) at the local OpenAI‑compatible endpoint that Foundry Local exposes, so every conversation and audio transcription stays on your device and can leverage the Snapdragon X Elite/X Plus NPU.

## Prerequisites

- Windows 11 Copilot+ PC with Snapdragon X Plus/Elite NPU.
- [Foundry Local](https://github.com/microsoft/Foundry-Local) installed (`winget install Microsoft.FoundryLocal`).
- At least one chat model available locally (for example `phi-3.5-mini`, `qwen2.5-0.5b`).
- Docker Desktop (for running Open WebUI container) or another runtime that can host the image `ghcr.io/open-webui/open-webui`.

## Quick Start (Automated)

The fastest way to get everything running:

```powershell
cd samples/open-webui
.\start-local-ai.ps1
```

This script will:
- Start Foundry Local service
- Load AI models (phi-3.5-mini, qwen2.5-0.5b)
- Pull and launch Open WebUI container
- Optionally configure Whisper for speech-to-text

Then browse to `http://localhost:3000` and create your admin account.

To stop everything:
```powershell
.\stop-local-ai.ps1
```

---

## Manual Setup

### 1. Prepare Foundry Local

```powershell
# Ensure the Foundry Local background service is up
foundry service start

# Load your preferred models so the NPU-optimized variants stay in memory
foundry model load phi-3.5-mini
foundry model load qwen2.5-0.5b

# (Optional) verify endpoint details
foundry server status
```

> The status command prints the HTTP base URL (defaults to `http://localhost:5273/v1`) and confirms which models are loaded. Keep that URL handy; Open WebUI will call it as if it were the OpenAI API.

### 2. Launch Open WebUI against Foundry Local

#### Quick `docker run`

```powershell
docker run -d --name open-webui --restart=unless-stopped `
  -p 3000:8080 `
  -e OPENAI_API_BASE_URL="http://host.docker.internal:5273/v1" `
  -e OPENAI_API_KEY="local-key" `
  -e ENABLE_SIGNUP="false" `
  -v "$Env:LOCALAPPDATA\open-webui:/app/backend/data" `
  ghcr.io/open-webui/open-webui:main
```

- `host.docker.internal` lets the Linux container reach the Windows host where Foundry Local runs.
- The API key value is ignored by Foundry Local but Open WebUI expects something non-empty.
- Mounting `LOCALAPPDATA` keeps your WebUI settings and chats persistent.

#### Docker Compose

This repository includes `samples/open-webui/docker-compose.yml` with the same settings. From this folder run:

```powershell
cd samples/open-webui
docker compose up -d
```

### 3. Point Open WebUI at your local models

1. Browse to `http://localhost:3000` and create the initial admin account.
2. Go to **Admin > Settings > Providers** and confirm "OpenAI Compatible" is enabled. The defaults use the env vars we just set.
3. Under **Models**, add entries that match the IDs reported by `foundry model ls --details`. Example:
   - **Name**: `phi-3.5-mini`
   - **Model ID**: `phi-3.5-mini-instruct-generic-npu`
   - **Provider**: OpenAI Compatible
4. Repeat for `qwen2.5-0.5b` or any other aliases you plan to keep loaded.

Start a chat and select one of the new models—responses should stream instantly from Foundry Local. You can tail the Foundry logs to verify requests land locally:

```powershell
foundry server logs --tail 50
```

### 4. Optional: Local Whisper integration

To enable speech input/transcription without leaving the device:

1. Load an audio-capable model in Foundry Local (for example `whisper-small`):
   ```powershell
   foundry model load whisper-small
   ```
2. Add the following env vars before launching Open WebUI:
   ```text
   WHISPER_API_BASE_URL=http://host.docker.internal:5273/v1
   WHISPER_API_KEY=local-key
   ```
3. Restart the container. The microphone icon in Open WebUI now sends audio to Foundry Local's `/audio/transcriptions` endpoint.

### 5. Tailor the experience (personas, finance workflows)

- Use Open WebUI's **Personas** feature to create a "Private Finance Advisor" system prompt that injects your desired guardrails.
- If you plan to ground answers in private data, build a small retrieval service alongside Foundry Local (for example using the `samples/rag` notebook) and register it as a Tool inside Open WebUI. All services can run on localhost, keeping sensitive data on the device.
- Frontend tweaks (custom panels, charts) can be done by forking Open WebUI and editing its React components—this sample keeps the wiring focused on the local inference path.

With this setup every token stays on your Surface's NPU, delivering low-latency chat through a familiar web UI while remaining completely offline.
