# Private RAG for Healthcare & Finance

A lightweight, fully offline RAG (Retrieval-Augmented Generation) system for sensitive personal documents like medical records, financial statements, and tax documents.

## Architecture

```
Your Documents (PDF, TXT, MD, DOCX)
         |
         v
   [Admin UI] -----> Upload/Delete/Manage
         |
         v
   [Document Ingestion]
         |
         v
   [Qdrant Vector DB] <-- Local embeddings via sentence-transformers
         |
         v
   [RAG Query Tool] --> Foundry Local LLM --> Open WebUI
```

**All processing stays 100% on your device. No data leaves your machine.**

---

## Quick Start (Docker - Recommended)

The easiest way to run the full stack with the admin UI:

```powershell
cd samples/open-webui/private-rag
.\start-full-stack.ps1 -Build -Detached
```

This starts:
| Service | URL | Purpose |
|---------|-----|---------|
| **RAG Admin UI** | http://localhost:8501 | Upload, view, delete documents |
| RAG API Server | http://localhost:8000 | Query API for Open WebUI |
| Qdrant | http://localhost:6333 | Vector database |

Then open **http://localhost:8501** to manage your documents.

### Stop the Stack

```powershell
docker compose down
```

---

## Manual Setup (Without Docker)

### 1. Start Qdrant (Vector Database)

```powershell
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 `
  -v "$Env:LOCALAPPDATA\qdrant:/qdrant/storage" `
  qdrant/qdrant
```

### 2. Install Python Dependencies

```powershell
cd samples/open-webui/private-rag
pip install -r requirements.txt
```

### 3. Add Your Documents

Place your private documents in the `documents/` folder:
- `documents/healthcare/` - Medical records, lab results, prescriptions
- `documents/finance/` - Bank statements, tax returns, investment reports

### 4. Ingest Documents

```powershell
python ingest.py
```

### 5. Start the RAG API Server

```powershell
python rag_server.py
```

The RAG server runs at `http://localhost:8000`.

### 6. Register as Open WebUI Tool

1. Open http://localhost:3000 (Open WebUI)
2. Go to **Workspace > Tools**
3. Click **+ Create Tool**
4. Paste the code from `openwebui_tool.py`

---

## Admin UI Features

The web-based admin UI (http://localhost:8501) provides:

- **Upload Tab**: Drag & drop files, select category, save & ingest
- **Indexed Documents Tab**: View all documents in the vector store, delete individual documents
- **Local Files Tab**: Browse files on disk, delete files and their vectors
- **Stats Sidebar**: Vector count, collection status
- **Quick Actions**: Refresh, clear all vectors, re-index

![Admin UI Screenshot](./admin/screenshot.png)

---

## File Structure

```
private-rag/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── config.py                 # Configuration settings
├── ingest.py                 # Document ingestion script
├── rag_server.py             # FastAPI RAG server
├── openwebui_tool.py         # Open WebUI tool integration
├── start-rag.ps1             # Simple startup (no admin UI)
├── start-full-stack.ps1      # Full stack with admin UI
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile.server         # RAG server container
├── admin/                    # Admin UI
│   ├── app.py                # Streamlit application
│   └── Dockerfile            # Admin container
└── documents/                # Your private documents
    ├── healthcare/           # Medical records
    └── finance/              # Financial documents
```

---

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `CHUNK_SIZE` | 500 | Words per chunk |
| `CHUNK_OVERLAP` | 100 | Overlap between chunks |
| `TOP_K` | 5 | Number of chunks to retrieve |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local embedding model |
| `QDRANT_HOST` | `localhost` | Qdrant server host |
| `QDRANT_PORT` | `6333` | Qdrant server port |

---

## Supported Document Types

- **Text**: `.txt`, `.md`
- **PDF**: `.pdf` (requires `pypdf`)
- **Office**: `.docx` (requires `python-docx`)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/query` | RAG query with LLM response |
| `POST` | `/search` | Semantic search only (no LLM) |
| `POST` | `/ingest` | Trigger document ingestion |
| `DELETE` | `/documents/{path}` | Delete document vectors |
| `GET` | `/stats` | Collection statistics |
| `GET` | `/categories` | List document categories |
| `GET` | `/health` | Health check |

Interactive API docs: http://localhost:8000/docs

---

## Privacy & Security

- All embeddings generated locally using sentence-transformers
- All LLM inference via Foundry Local (NPU-accelerated)
- Vector database stored locally in Docker volume or `%LOCALAPPDATA%\qdrant`
- No internet connection required after initial setup
- Documents never leave your device

---

## Example Queries

Once set up, you can ask questions like:

**Healthcare:**
- "What were my cholesterol levels in my last blood test?"
- "Summarize my recent doctor visit notes"
- "What medications am I currently prescribed?"

**Finance:**
- "What was my total income last year?"
- "Summarize my investment portfolio performance"
- "What tax deductions did I claim?"

---

## Deleting Documents

### Via Admin UI (Recommended)
1. Open http://localhost:8501
2. Go to "Indexed Documents" tab
3. Click the trash icon next to any document

### Via API
```powershell
curl -X DELETE "http://localhost:8000/documents/documents/healthcare/myfile.pdf"
```

### Clear Everything
```powershell
# Remove all vectors (keeps files)
docker exec -it qdrant curl -X DELETE "http://localhost:6333/collections/private_docs"

# Or remove the container entirely
docker compose down -v
```

---

## Troubleshooting

### Qdrant not starting
```powershell
# Check if port is in use
netstat -ano | findstr "6333"
# Stop existing container
docker stop qdrant && docker rm qdrant
```

### Admin UI not loading
```powershell
# Check container logs
docker logs rag-admin
```

### Slow embedding generation
The first run downloads the embedding model (~90MB). Subsequent runs are faster.

### Out of memory
Reduce `CHUNK_SIZE` in `config.py` or process fewer documents at once.

### Connection refused errors
Ensure all containers are on the same Docker network:
```powershell
docker compose ps  # Check all services are running
docker compose logs  # View logs
```
