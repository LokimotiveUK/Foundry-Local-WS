# Sample: Open WebUI + Foundry Local

This sample shows how to point [Open WebUI](https://github.com/open-webui/open-webui) at the local OpenAI-compatible endpoint that Foundry Local exposes, so every conversation and audio transcription stays on your device and can leverage the Snapdragon X Elite/X Plus NPU.

## Prerequisites

- Windows 11 Copilot+ PC with Snapdragon X Plus/Elite NPU.
- [Foundry Local](https://github.com/microsoft/Foundry-Local) installed (`winget install Microsoft.FoundryLocal`).
- At least one chat model available locally (for example `phi-3.5-mini`, `qwen2.5-0.5b`).
- Docker Desktop (for running Open WebUI container) or another runtime that can host the image `ghcr.io/open-webui/open-webui`.

## Quick Start (Docker Compose - Recommended)

The easiest way to get everything running with **automatic port handling**:

```powershell
cd samples/open-webui
docker compose up -d
```

This starts two services:
- **foundry-proxy**: Auto-discovers Foundry's dynamic port (no manual configuration needed)
- **open-webui**: ChatGPT-like interface at http://localhost:3000

The proxy automatically detects Foundry's port on every request, so you never need to manually update port numbers when Foundry restarts.

Then browse to `http://localhost:3000` and create your admin account.

### Stop Everything

```powershell
docker compose down
```

---

## Alternative: PowerShell Scripts

For more control over the startup process:

```powershell
cd samples/open-webui
.\start-local-ai.ps1
```

This script will:
- Start Foundry Local service
- Automatically detect the Foundry endpoint port
- Load AI models (phi-3.5-mini, qwen2.5-0.5b)
- Pull and launch Open WebUI container with the correct port
- Optionally configure Whisper for speech-to-text

For non-interactive automation (CI/CD or scripting):
```powershell
.\start-local-ai-auto.ps1
# Or with Whisper enabled:
.\start-local-ai-auto.ps1 -EnableWhisper
```

To stop everything:
```powershell
.\stop-local-ai.ps1
```

---

## How the Foundry Proxy Works

Foundry Local uses **dynamic ports** that change on each service restart (e.g., 50402, 62873, 57537). This created a problem where Open WebUI would lose connection after Foundry restarts.

The `foundry-proxy` service solves this by:

1. **Scanning port ranges** (50400-50500, 50000-50050, etc.) to find Foundry
2. **Caching the discovered port** for 10 seconds for performance
3. **Auto-retrying** if Foundry moves to a new port
4. **Providing a stable endpoint** (`foundry-proxy:8080`) for Open WebUI

**Architecture:**
```
Open WebUI --> foundry-proxy:8080 --> (auto-discovers) --> Foundry Local:50402
```

---

## Manual Setup

### 1. Prepare Foundry Local

```powershell
# Ensure the Foundry Local background service is up
foundry service start

# Load your preferred models so the NPU-optimized variants stay in memory
foundry model run phi-3.5-mini
foundry model run qwen2.5-0.5b

# Check the service status to find the endpoint port
foundry service status
```

### 2. Launch Open WebUI against Foundry Local

#### Quick `docker run`

Replace `<PORT>` with the port number from `foundry service status`:

```powershell
docker run -d --name open-webui --restart=unless-stopped `
  -p 3000:8080 `
  -e OPENAI_API_BASE_URL="http://host.docker.internal:<PORT>/v1" `
  -e OPENAI_API_KEY="local-key" `
  -e ENABLE_SIGNUP="false" `
  -v "$Env:LOCALAPPDATA\open-webui:/app/backend/data" `
  ghcr.io/open-webui/open-webui:main
```

- `host.docker.internal` lets the Linux container reach the Windows host where Foundry Local runs.
- The API key value is ignored by Foundry Local but Open WebUI expects something non-empty.
- Mounting `LOCALAPPDATA` keeps your WebUI settings and chats persistent.

### 3. Point Open WebUI at your local models

1. Browse to `http://localhost:3000` and create the initial admin account.
2. Go to **Admin > Settings > Providers** and confirm "OpenAI Compatible" is enabled. The defaults use the env vars we just set.
3. Under **Models**, add entries that match the IDs reported by `foundry model list`. Example:
   - **Name**: `phi-3.5-mini`
   - **Model ID**: `phi-3.5-mini-instruct-generic-npu`
   - **Provider**: OpenAI Compatible
4. Repeat for `qwen2.5-0.5b` or any other aliases you plan to keep loaded.

Start a chat and select one of the new models—responses should stream instantly from Foundry Local.

### 4. Optional: Local Whisper integration

To enable speech input/transcription without leaving the device:

1. Load an audio-capable model in Foundry Local (for example `whisper-small`):
   ```powershell
   foundry model run whisper-small
   ```
2. Add the following env vars before launching Open WebUI (replace `<PORT>` with your Foundry port):
   ```text
   WHISPER_API_BASE_URL=http://host.docker.internal:<PORT>/v1
   WHISPER_API_KEY=local-key
   ```
3. Restart the container. The microphone icon in Open WebUI now sends audio to Foundry Local's `/audio/transcriptions` endpoint.

### 5. Tailor the experience (personas, finance workflows)

- Use Open WebUI's **Personas** feature to create a "Private Finance Advisor" system prompt that injects your desired guardrails.
- If you plan to ground answers in private data, build a small retrieval service alongside Foundry Local (for example using the `samples/rag` notebook) and register it as a Tool inside Open WebUI. All services can run on localhost, keeping sensitive data on the device.
- Frontend tweaks (custom panels, charts) can be done by forking Open WebUI and editing its React components—this sample keeps the wiring focused on the local inference path.

With this setup every token stays on your Surface's NPU, delivering low-latency chat through a familiar web UI while remaining completely offline.

---

## Private RAG for Healthcare & Finance

For sensitive personal documents (medical records, tax returns, financial statements), we provide a lightweight RAG system that runs 100% locally with a web-based admin UI for document management.

### Quick Start (Docker Compose - Recommended)

```powershell
cd samples/open-webui/private-rag
docker compose up -d --build
```

This starts three services:

| Service | URL | Purpose |
|---------|-----|---------|
| **RAG Admin UI** | http://localhost:8501 | Upload, view, delete documents |
| RAG API Server | http://localhost:8000 | Query API for Open WebUI |
| Qdrant | http://localhost:6333 | Vector database |

The RAG server also auto-discovers Foundry's dynamic port, so no manual configuration is needed.

### Admin UI Features

The web-based admin UI at **http://localhost:8501** provides:

- **Upload Tab**: Drag & drop files, select category (healthcare/finance), save & ingest
- **Indexed Documents Tab**: View all documents in the vector store, delete individual documents
- **Local Files Tab**: Browse files on disk, delete files and their vectors
- **Stats Sidebar**: Vector count, collection status, quick actions

### Add Your Documents

Place files in the `private-rag/documents/` folder:
- `documents/healthcare/` - Medical records, lab results, prescriptions
- `documents/finance/` - Bank statements, tax returns, investments

Supported formats: `.txt`, `.md`, `.pdf`, `.docx`

Or use the Admin UI to upload files directly via drag & drop.

### Use in Open WebUI

1. Go to **Workspace > Tools** in Open WebUI
2. Click **+ Create Tool**
3. Paste the code from `private-rag/openwebui_tool.py`
4. Save and enable the tool

Now you can ask questions like:
- "What were my cholesterol levels in my last blood test?"
- "What was my total income last year?"
- "Summarize my recent doctor visit notes"

### Stop the RAG Stack

```powershell
cd samples/open-webui/private-rag
docker compose down
```

See [private-rag/README.md](./private-rag/README.md) for full documentation.

---

## File Structure

```
open-webui/
├── README.md                 # This file
├── docker-compose.yml        # Docker Compose with auto-port proxy
├── foundry-proxy/            # Auto-discovers Foundry's dynamic port
│   ├── Dockerfile
│   └── proxy.py
├── start-local-ai.ps1        # Interactive startup script
├── start-local-ai-auto.ps1   # Non-interactive startup
├── stop-local-ai.ps1         # Stop all services
└── private-rag/              # Private RAG system
    ├── README.md
    ├── docker-compose.yml
    ├── rag_server.py
    ├── admin/
    └── documents/
```

---

## Troubleshooting

### Models not appearing in Open WebUI
- Check that Foundry is running: `foundry service status`
- Check the proxy logs: `docker logs foundry-proxy`
- The proxy scans common port ranges - ensure Foundry is on a standard port
- Restart the proxy: `docker compose restart foundry-proxy`

### "Backend Required" error
- Clear browser cache or use incognito mode
- Ensure you're accessing `http://localhost:3000` (not https)
- Wait a few seconds for the container to fully start

### Foundry port not being discovered
Check the proxy logs to see which port was found:
```powershell
docker logs foundry-proxy
```

If Foundry is on an unusual port, the proxy will scan these ranges:
- 50400-50500 (most common)
- 50000-50100
- 51400-51500
- 62800-62900
- 5273-5280

### RAG queries returning errors
- Check RAG server health: `curl http://localhost:8000/health`
- Verify the model is working: The health endpoint shows `foundry_status` and `model`
- Check logs: `docker logs rag-server`
