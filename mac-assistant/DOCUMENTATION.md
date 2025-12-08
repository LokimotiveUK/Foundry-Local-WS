# Mac Assistant - Complete Technical Documentation

> **Version:** 1.0.0
> **Last Updated:** December 2024
> **Status:** Fully Developed

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Backend API](#backend-api)
5. [RAG System](#rag-system)
6. [Storage Layer](#storage-layer)
7. [Desktop UI](#desktop-ui)
8. [Configuration](#configuration)
9. [API Reference](#api-reference)
10. [Running the Application](#running-the-application)

---

## Project Overview

### What is Mac Assistant?

Mac Assistant is a **100% local** AI desktop assistant for macOS that combines:

- **On-device AI inference** via Microsoft Foundry Local SDK
- **RAG (Retrieval-Augmented Generation)** with specialized knowledge pockets
- **Persistent chat history** with SQLite storage
- **Native desktop UI** built with Electron
- **Real-time streaming** responses with performance metrics

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **100% Local** | No cloud dependencies - all AI inference happens on-device |
| **Privacy First** | All data stored locally in SQLite, no telemetry |
| **Modular Architecture** | Separate concerns: API, RAG, Storage, UI |
| **Performance Visibility** | Real-time tokens/second monitoring |
| **Extensible RAG** | Pluggable "pockets" for domain-specific knowledge |

### Technology Stack

| Layer | Technology |
|-------|------------|
| AI Inference | Microsoft Foundry Local SDK |
| Speech-to-Text | OpenAI Whisper (via faster-whisper) |
| Backend API | FastAPI (Python 3.10+) |
| Database | SQLite + SQLAlchemy |
| Vector Store | Qdrant (embedded mode) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Desktop UI | Electron 28 |
| Frontend | Vanilla JS + CSS (no framework dependencies) |

---

## Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     DESKTOP UI (Electron)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Chat View   │  │   Sidebar    │  │   Settings   │           │
│  │  - Messages  │  │  - Sessions  │  │  - Model     │           │
│  │  - Streaming │  │  - Pockets   │  │  - Theme     │           │
│  │  - Metrics   │  │  - Search    │  │  - Params    │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         │                 │                  │                   │
│         └─────────────────┼──────────────────┘                   │
│                           │ HTTP/WebSocket                       │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    API Routes                            │    │
│  │  /chat    /models    /settings    /rag    /export       │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│  ┌─────────────┬───────────┼───────────┬─────────────┐          │
│  │             │           │           │             │          │
│  ▼             ▼           ▼           ▼             ▼          │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐         │
│ │Foundry │ │  RAG   │ │Storage │ │Settings│ │ Export │         │
│ │Manager │ │Retriever│ │ Layer │ │  Repo  │ │Service │         │
│ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘         │
│     │          │          │          │          │               │
│     │     ┌────┴────┐     │          │          │               │
│     │     │         │     │          │          │               │
│     │     ▼         ▼     ▼          ▼          ▼               │
│     │  ┌──────┐ ┌──────┐ ┌────────────────────────┐             │
│     │  │Qdrant│ │Embed │ │     SQLite Database    │             │
│     │  │Vector│ │Model │ │  - chat_sessions       │             │
│     │  │Store │ │      │ │  - chat_messages       │             │
│     │  └──────┘ └──────┘ │  - documents           │             │
│     │                    │  - settings            │             │
│     │                    │  - exports             │             │
│     │                    └────────────────────────┘             │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FOUNDRY LOCAL SDK                            │   │
│  │  - OpenAI-compatible API                                  │   │
│  │  - On-device inference (Apple Silicon optimized)          │   │
│  │  - Model management (load/unload/switch)                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Input → Desktop UI → FastAPI → RAG Retrieval → Foundry SDK → Response Stream
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Vector Search      │
                              │  (Qdrant + Embed)   │
                              └─────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │  Context Injection  │
                              │  into Prompt        │
                              └─────────────────────┘
```

---

## Directory Structure

```
mac-assistant/
│
├── src/                          # Python backend source
│   ├── __init__.py              # Version: 1.0.0
│   │
│   ├── core/                    # Core models and configuration
│   │   ├── __init__.py
│   │   ├── config.py            # Settings, DEFAULT_POCKETS
│   │   ├── models.py            # Pydantic models (ChatMessage, etc.)
│   │   └── exceptions.py        # Custom exceptions
│   │
│   ├── foundry/                 # Foundry Local SDK integration
│   │   ├── __init__.py
│   │   ├── manager.py           # FoundryManager class
│   │   ├── metrics.py           # MetricsTracker for tokens/sec
│   │   └── streaming.py         # StreamingHandler for async chat
│   │
│   ├── rag/                     # RAG (Retrieval-Augmented Generation)
│   │   ├── __init__.py
│   │   ├── pockets.py           # PocketManager (CRUD for pockets)
│   │   ├── embeddings.py        # EmbeddingService (sentence-transformers)
│   │   ├── vector_store.py      # VectorStore (Qdrant integration)
│   │   ├── chunker.py           # DocumentChunker (text splitting)
│   │   ├── ingest.py            # IngestionService (document processing)
│   │   └── retriever.py         # RAGRetriever (query + generate)
│   │
│   ├── storage/                 # SQLite persistence layer
│   │   ├── __init__.py          # Exports all storage classes
│   │   ├── database.py          # Database class, session management
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── chats.py             # ChatRepository
│   │   ├── documents.py         # DocumentRepository
│   │   ├── settings.py          # SettingsRepository
│   │   └── export.py            # ExportService (backup/restore)
│   │
│   ├── api/                     # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory, lifespan
│   │   ├── websocket.py         # WebSocket endpoints
│   │   └── routes/              # API route modules
│   │       ├── __init__.py
│   │       ├── chat.py          # /chat endpoints
│   │       ├── models.py        # /models endpoints
│   │       ├── settings.py      # /settings endpoints
│   │       ├── rag.py           # /rag endpoints
│   │       └── export.py        # /export endpoints
│   │
│   └── cli/                     # CLI tools (placeholder)
│       └── __init__.py
│
├── desktop/                     # Desktop UI
│   └── electron/
│       ├── package.json         # Electron dependencies
│       ├── main.js              # Electron main process
│       ├── preload.js           # Secure IPC bridge
│       ├── assets/
│       │   └── icon.svg         # App icon
│       └── src/
│           ├── index.html       # Main UI structure
│           ├── styles.css       # CSS with dark/light themes
│           └── app.js           # Frontend application logic
│
├── data/                        # Data directory (created at runtime)
│   └── pockets/                 # RAG pocket document storage
│       ├── medical/
│       ├── finance/
│       ├── study/
│       └── writing/
│
├── pyproject.toml               # Python project configuration
├── requirements.txt             # Python dependencies
├── start.sh                     # Combined launcher script
├── README.md                    # User-facing documentation
└── DOCUMENTATION.md             # This file
```

---

## Backend API

### FastAPI Application

**Entry Point:** `src/api/main.py`

The application uses FastAPI's lifespan context manager for initialization:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize SQLite database
    init_database()

    # 2. Initialize Foundry Local SDK
    manager = initialize_foundry(settings.default_model)

    yield  # Application runs

    # Cleanup on shutdown
```

### Middleware

- **CORS**: Configured for local connections
  - Origins: `localhost:*`, `127.0.0.1:*`, `tauri://localhost`, `file://*`
  - Credentials: Enabled
  - Methods/Headers: All allowed

### Included Routers

| Router | Prefix | Description |
|--------|--------|-------------|
| `chat_router` | `/chat` | Chat messaging and sessions |
| `models_router` | `/models` | Model management |
| `settings_router` | `/settings` | Application settings |
| `rag_router` | `/rag` | RAG operations |
| `export_router` | `/export` | Data export/import |
| `speech_router` | `/speech` | Speech-to-text (Whisper) |
| `websocket_router` | `/ws` | WebSocket endpoints |

---

## Speech-to-Text (Whisper)

### Overview

Mac Assistant includes local speech-to-text using OpenAI's Whisper model via the `faster-whisper` library. All transcription happens on-device.

### Whisper Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `tiny` | ~75MB | Fastest | Basic | Quick dictation |
| `base` | ~150MB | Fast | Good | **Default - balanced** |
| `small` | ~500MB | Medium | Better | Longer recordings |
| `medium` | ~1.5GB | Slow | High | Professional use |
| `large-v3` | ~3GB | Slowest | Best | Maximum accuracy |

### Features

- **Auto language detection**: Supports 99 languages
- **Voice Activity Detection**: Filters silence automatically
- **Streaming support**: Process audio in real-time
- **Multiple formats**: WAV, MP3, M4A, FLAC, OGG, WEBM

### Desktop UI Integration

The desktop UI includes a microphone button for voice input:

1. **Click** the microphone button to start recording
2. **Click again** to stop and transcribe
3. Transcribed text is inserted into the message input
4. Recording time is shown in the footer

### Speech Module Structure

```
src/speech/
├── __init__.py
└── transcriber.py     # WhisperTranscriber class
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/speech/transcribe` | POST | Transcribe uploaded audio file |
| `/speech/transcribe/base64` | POST | Transcribe base64-encoded audio |
| `/speech/models` | GET | List available Whisper models |
| `/speech/status` | GET | Get transcriber status |
| `/speech/initialize` | POST | Pre-load Whisper model |
| `/speech/languages` | GET | List supported languages |

---

## RAG System

### Overview

The RAG system enables AI responses grounded in user documents through:

1. **Document Ingestion**: PDF, TXT, MD files chunked and embedded
2. **Vector Storage**: Embeddings stored in Qdrant (embedded mode)
3. **Semantic Search**: Query embeddings matched against document embeddings
4. **Context Injection**: Retrieved chunks injected into AI prompt

### RAG Pockets

Pockets are isolated document collections with custom configurations:

| Pocket | Chunk Size | Use Case |
|--------|------------|----------|
| `medical` | 400 tokens | Medical records, lab results |
| `finance` | 600 tokens | Bank statements, tax documents |
| `study` | 500 tokens | Textbooks, research papers |
| `writing` | 800 tokens | Manuscripts, creative writing |

### Pocket Configuration

```python
DEFAULT_POCKETS = {
    "medical": {
        "name": "Medical Records",
        "description": "Personal health information",
        "chunk_size": 400,
        "chunk_overlap": 50,
        "system_prompt": "You are a medical information assistant..."
    },
    # ... other pockets
}
```

### RAG Pipeline

```
Document Upload
      │
      ▼
┌─────────────┐
│  Chunker    │  Split into overlapping chunks
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Embedder   │  Generate 384-dim embeddings
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Qdrant     │  Store vectors with metadata
└─────────────┘

Query Flow:
User Query → Embed → Vector Search → Top-K Chunks → Context + Query → LLM → Response
```

### Embedding Model

- **Model**: `all-MiniLM-L6-v2` (sentence-transformers)
- **Dimensions**: 384
- **Runs locally**: No API calls required

### Vector Store

- **Engine**: Qdrant (embedded/in-memory mode)
- **Collections**: One per pocket
- **Distance Metric**: Cosine similarity
- **Persistence**: Optional disk storage

---

## Storage Layer

### Database Schema

```sql
-- Chat Sessions
CREATE TABLE chat_sessions (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255) DEFAULT 'New Chat',
    model VARCHAR(100) NOT NULL,
    rag_pocket VARCHAR(50),
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat Messages
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(36) REFERENCES chat_sessions(id),
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens_generated INTEGER,
    tokens_per_second FLOAT,
    total_time FLOAT,
    sources_json TEXT  -- JSON array of RAG sources
);

-- Documents (RAG metadata)
CREATE TABLE documents (
    id VARCHAR(36) PRIMARY KEY,
    pocket_id VARCHAR(50) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    path TEXT NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    chunk_count INTEGER DEFAULT 0,
    is_indexed BOOLEAN DEFAULT FALSE,
    indexed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings (key-value store)
CREATE TABLE settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Exports (backup history)
CREATE TABLE exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(255) NOT NULL,
    export_type VARCHAR(50) NOT NULL,
    size_bytes INTEGER,
    item_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Repositories

| Repository | Purpose |
|------------|---------|
| `ChatRepository` | CRUD for sessions/messages, search, export |
| `DocumentRepository` | Document metadata tracking |
| `SettingsRepository` | Key-value settings with type coercion |
| `ExportService` | Full/partial data export and import |

### Database Location

```
~/.mac-assistant/
├── mac_assistant.db      # SQLite database
├── config.json           # User configuration
└── exports/              # Export files
```

---

## Desktop UI

### Electron Architecture

```
┌─────────────────────────────────────────┐
│           Main Process (main.js)         │
│  - Window management                     │
│  - Native menus                          │
│  - IPC handlers                          │
│  - electron-store persistence            │
└───────────────┬─────────────────────────┘
                │ IPC (contextBridge)
                │
┌───────────────▼─────────────────────────┐
│         Preload Script (preload.js)      │
│  - Secure API exposure                   │
│  - Event listeners                       │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│         Renderer Process (app.js)        │
│  - UI logic                              │
│  - API communication                     │
│  - Stream handling                       │
└─────────────────────────────────────────┘
```

### UI Components

| Component | File | Description |
|-----------|------|-------------|
| Title Bar | `index.html` | macOS-style with connection status |
| Sidebar | `index.html` | Session list, pocket selector, settings |
| Chat Area | `index.html` | Messages, streaming, metrics |
| Input Area | `index.html` | Textarea with send/stop buttons |
| Settings Modal | `index.html` | Configuration options |
| Sources Modal | `index.html` | RAG source citations |
| Model Manager | `index.html` | Download, switch, delete models |

### Chat Features

- **Stop Generation**: Red stop button appears during AI response generation. Click to abort the stream mid-response.
- **Message Input**: Enter sends message, Shift+Enter adds new line
- **Streaming**: Real-time token display with performance metrics

### Styling

- **CSS Variables**: Full theming support
- **Dark/Light Modes**: System-aware or manual
- **Native Feel**: macOS-inspired design
- **Responsive**: Collapsible sidebar on narrow screens

### Theme Variables

```css
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f7;
  --text-primary: #1d1d1f;
  --accent-color: #007aff;
  /* ... 30+ CSS variables */
}

[data-theme="dark"] {
  --bg-primary: #1c1c1e;
  --bg-secondary: #2c2c2e;
  --text-primary: #f5f5f7;
  /* ... dark overrides */
}
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `⌘N` | New chat |
| `⌘M` | Toggle metrics panel |
| `⌘\` | Toggle sidebar |
| `⌘,` | Open settings |
| `⌘E` | Export data |
| `⌘I` | Import data |
| `Enter` | Send message |
| `Shift+Enter` | New line in message |

### Menu Bar

```
Mac Assistant
├── About Mac Assistant
├── Preferences... (⌘,)
├── Services
├── Hide/Quit

File
├── New Chat (⌘N)
├── Export Data... (⌘E)
├── Import Data... (⌘I)
├── Close Window

Edit
├── Undo/Redo
├── Cut/Copy/Paste
├── Select All

View
├── Toggle Sidebar (⌘\)
├── Toggle Metrics (⌘M)
├── Reload/DevTools
├── Zoom controls

RAG
├── Medical Pocket
├── Finance Pocket
├── Study Pocket
├── Writing Pocket
├── No Pocket (General)

Window
├── Minimize/Zoom
├── Bring All to Front

Help
├── Documentation
├── API Docs
```

---

## Configuration

### Environment Settings (`src/core/config.py`)

```python
class Settings:
    # API Server
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # AI Model
    default_model: str = "qwen2.5-1.5b-instruct"
    temperature: float = 0.7
    max_response_tokens: int = 2048
    context_window: int = 10

    # RAG
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 5
    min_similarity: float = 0.3

    # Features
    verbose_mode: bool = True

    # Paths
    app_dir: Path = ~/.mac-assistant/
    data_dir: Path = ./data/
```

### Electron Settings (`electron-store`)

```javascript
{
  windowBounds: { width: 1200, height: 800 },
  apiPort: 8000,
  theme: 'system',  // 'system' | 'light' | 'dark'
  sidebarWidth: 280,
  showMetrics: true
}
```

---

## API Reference

### Chat Endpoints

#### `POST /chat`
Send a message and receive complete response.

**Request:**
```json
{
  "message": "What is machine learning?",
  "session_id": "optional-uuid",
  "rag_pocket": "study",
  "temperature": 0.7,
  "max_tokens": 2048,
  "include_history": true
}
```

**Response:**
```json
{
  "message": "Machine learning is...",
  "session_id": "uuid",
  "model": "qwen2.5-1.5b-instruct",
  "rag_pocket": "study",
  "sources": [
    {
      "index": 1,
      "document": "ml_textbook.pdf",
      "score": 0.87,
      "text_preview": "..."
    }
  ],
  "metrics": {
    "tokens_generated": 150,
    "tokens_per_second": 45.2,
    "total_time": 3.32
  }
}
```

#### `POST /chat/stream`
Stream response via Server-Sent Events.

**Events:**
- `sources`: RAG sources (sent first if applicable)
- `data`: Token chunks with metrics
- `metadata`: Final session info
- `error`: Error information

#### `GET /chat/sessions`
List all chat sessions.

**Query Parameters:**
- `rag_pocket`: Filter by pocket
- `limit`: Max results (default 50)
- `offset`: Pagination offset

#### `GET /chat/sessions/{session_id}`
Get session with full message history.

#### `GET /chat/sessions/{session_id}/messages`
Get messages for a session.

#### `PATCH /chat/sessions/{session_id}`
Update session title or archive status.

#### `DELETE /chat/sessions/{session_id}`
Delete a session.

#### `GET /chat/search`
Search messages across sessions.

**Query Parameters:**
- `query`: Search text (required)
- `rag_pocket`: Filter by pocket
- `limit`: Max results

### WebSocket `/ws/chat`

**Client → Server:**
```json
{
  "type": "message",
  "content": "Hello!",
  "session_id": "optional-uuid",
  "rag_pocket": "medical",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**Server → Client:**
```json
// Connection
{ "type": "connected", "client_id": "uuid", "foundry_ready": true }

// Stream start
{ "type": "start", "session_id": "uuid", "model": "qwen..." }

// Token chunks
{ "type": "chunk", "content": "Hello", "done": false, "metrics": {...} }

// Complete
{ "type": "complete", "session_id": "uuid", "metrics": {...} }

// Error
{ "type": "error", "message": "Error description" }
```

### Model Endpoints

#### `GET /models`
Get current model info.

#### `GET /models/available`
List all available models.

#### `GET /models/loaded`
List currently loaded models.

#### `GET /models/cached`
List cached models.

#### `POST /models/switch`
Switch to a different model.

```json
{ "model": "phi-3-mini" }
```

#### `POST /models/unload`
Unload a model from memory.

#### `POST /models/download/{model_alias}`
Download a model to local cache (async with progress tracking).

**Query Parameters:**
- `force`: Force re-download if already cached
- `blocking`: If true, wait for completion (default: false for async)

**Response (async):**
```json
{
  "status": "started",
  "alias": "phi-4-mini",
  "model_id": "microsoft/phi-4-mini",
  "expected_size_mb": 5713,
  "message": "Download started. Poll /models/downloads/{alias}/status for progress."
}
```

#### `GET /models/downloads/{model_alias}/status`
Get real-time download progress for a model.

**Response:**
```json
{
  "alias": "phi-4-mini",
  "status": "downloading",
  "progress_percent": 45,
  "downloaded_mb": 2571.0,
  "new_mb": 2571.0,
  "expected_size_mb": 5713
}
```

#### `DELETE /models/cache/{model_alias}`
Delete a downloaded model from disk to free storage space.

**Response:**
```json
{
  "status": "deleted",
  "model": "phi-4-mini",
  "path": "/Users/.../.foundry/cache/models/Microsoft/...",
  "freed_mb": 5713.5
}
```

### RAG Endpoints

#### `GET /rag/pockets`
List all RAG pockets.

#### `POST /rag/pockets`
Create a new pocket.

#### `GET /rag/pockets/{pocket_id}`
Get pocket details.

#### `DELETE /rag/pockets/{pocket_id}`
Delete a pocket.

#### `POST /rag/pockets/{pocket_id}/documents/upload`
Upload a document.

#### `POST /rag/ingest`
Ingest documents into vector store.

```json
{
  "pocket_id": "medical",
  "reindex": false
}
```

#### `POST /rag/query`
RAG query with AI response.

```json
{
  "query": "What were my test results?",
  "pocket_id": "medical",
  "top_k": 5,
  "generate_response": true
}
```

#### `POST /rag/search`
Semantic search only (no AI).

#### `GET /rag/stats`
Get RAG system statistics.

### Settings Endpoints

#### `GET /settings`
Get all settings.

#### `GET /settings/{key}`
Get a specific setting.

#### `PUT /settings/{key}`
Update a setting.

#### `PUT /settings`
Batch update settings.

### Export Endpoints

#### `POST /export/all`
Export all data.

#### `POST /export/chats`
Export only chats.

#### `POST /export/settings`
Export only settings.

#### `POST /export/pocket/{pocket_id}`
Export pocket documents.

#### `GET /export/list`
List available exports.

#### `GET /export/download/{filename}`
Download an export file.

#### `DELETE /export/{filename}`
Delete an export.

#### `POST /export/import`
Import from uploaded file.

#### `POST /export/import/file`
Import from file path.

### Speech Endpoints

#### `POST /speech/transcribe`
Transcribe an uploaded audio file.

**Form Data:**
- `file`: Audio file (WAV, MP3, M4A, FLAC, OGG, WEBM)
- `language`: Optional language code (auto-detect if not specified)
- `task`: `transcribe` (keep language) or `translate` (to English)
- `include_segments`: Include word-level timestamps

**Response:**
```json
{
  "text": "Hello, this is a test recording.",
  "language": "en",
  "language_probability": 0.98,
  "duration": 3.5,
  "processing_time": 1.2,
  "words_per_minute": 120.5,
  "segments": [
    {
      "text": "Hello, this is a test recording.",
      "start": 0.0,
      "end": 3.5,
      "confidence": 0.95
    }
  ]
}
```

#### `POST /speech/transcribe/base64`
Transcribe base64-encoded audio (for web clients).

**Form Data:**
- `audio_base64`: Base64-encoded audio data
- `filename`: Original filename for format detection
- `language`: Optional language code
- `task`: `transcribe` or `translate`

#### `GET /speech/models`
List available Whisper models.

```json
{
  "models": {
    "tiny": {"size": "~75MB", "speed": "fastest", "quality": "lowest"},
    "base": {"size": "~150MB", "speed": "fast", "quality": "good"},
    "small": {"size": "~500MB", "speed": "medium", "quality": "better"},
    "medium": {"size": "~1.5GB", "speed": "slow", "quality": "high"},
    "large-v3": {"size": "~3GB", "speed": "slowest", "quality": "best"}
  },
  "default": "base",
  "recommended": {
    "fast": "tiny",
    "balanced": "base",
    "quality": "small",
    "best": "large-v3"
  }
}
```

#### `GET /speech/status`
Get current transcriber status.

```json
{
  "model_size": "base",
  "device": "cpu",
  "compute_type": "int8",
  "is_initialized": true,
  "model_info": {"size": "~150MB", "speed": "fast", "quality": "good"}
}
```

#### `POST /speech/initialize`
Pre-load a Whisper model (avoids delay on first transcription).

**Form Data:**
- `model_size`: Model to load (tiny, base, small, medium, large-v3)

#### `GET /speech/languages`
List commonly supported languages.

```json
{
  "common": ["en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko", ...],
  "note": "Whisper auto-detects language if not specified."
}
```

### Health & Metrics

#### `GET /health`
```json
{
  "status": "healthy",
  "foundry_running": true,
  "current_model": "qwen2.5-1.5b-instruct",
  "qdrant_status": "not_initialized",
  "version": "1.0.0"
}
```

#### `GET /metrics`
```json
{
  "foundry": {
    "initialized": true,
    "running": true,
    "current_model": "qwen2.5-1.5b-instruct"
  },
  "models": {
    "loaded_count": 1,
    "cached_count": 3
  },
  "api": {
    "version": "1.0.0"
  }
}
```

---

## Running the Application

### Prerequisites

1. **macOS 12+** (Apple Silicon recommended)
2. **Python 3.10+**
3. **Node.js 18+** (for desktop UI)
4. **Foundry Local**:
   ```bash
   brew install microsoft/foundrylocal/foundrylocal
   ```

### Installation

```bash
# Clone and enter directory
cd mac-assistant

# Install Python dependencies
pip install -e .

# Download an AI model
foundry model download qwen2.5-1.5b-instruct

# Install Electron dependencies
cd desktop/electron
npm install
cd ../..
```

### Running

#### Option 1: Combined Launcher
```bash
./start.sh
```

#### Option 2: Separate Processes

**Terminal 1 - Backend:**
```bash
python -m src.api.main
```

**Terminal 2 - Desktop UI:**
```bash
cd desktop/electron
npm start
```

#### Option 3: Development Mode

**Backend with auto-reload:**
```bash
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

**Electron with DevTools:**
```bash
cd desktop/electron
npm run dev
```

### Building for Distribution

```bash
cd desktop/electron

# Build macOS DMG
npm run build:mac

# Output: dist/Mac Assistant-1.0.0.dmg
```

---

## Recommended Models

| Model | Size | Best For |
|-------|------|----------|
| `qwen2.5-1.5b-instruct` | 1.5B | Fast responses, general use |
| `phi-3-mini` | 3.8B | Better reasoning |
| `llama-3.2-3b-instruct` | 3B | Balanced performance |
| `gemma-2-2b-it` | 2B | Efficient, good quality |

### Downloading Models

```bash
# List available models
foundry model list

# Download a model
foundry model download <model-name>

# Check cached models
foundry cache list
```

---

## Performance Considerations

### Memory Usage

- **Backend**: ~200MB base + model size
- **Qdrant**: ~50MB + vectors
- **Electron**: ~150MB

### Optimization Tips

1. Use smaller models (1.5B-3B) for faster inference
2. Reduce `context_window` for lower memory usage
3. Use `chunk_size` of 300-500 for better RAG retrieval
4. Disable `verbose_mode` to reduce logging overhead

### Apple Silicon Optimization

Foundry Local automatically uses Metal acceleration on Apple Silicon Macs. No additional configuration required.

---

## Security Notes

1. **Local Only**: All data stays on your machine
2. **No Telemetry**: No usage data sent anywhere
3. **Sandboxed Electron**: Context isolation enabled
4. **CSP Headers**: Strict Content Security Policy
5. **CORS Restricted**: Only localhost connections allowed

---

## Future Enhancements (Not Implemented)

- [ ] SwiftUI native macOS app
- [ ] Voice input/output
- [ ] Document OCR support
- [ ] Multi-modal image support
- [ ] Plugin system
- [ ] Spotlight integration
- [ ] Menu bar quick access

---

*Documentation generated for Mac Assistant v1.0.0*
