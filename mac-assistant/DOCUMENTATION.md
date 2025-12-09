# Mac Assistant - Complete Technical Documentation

> **Version:** 1.1.0
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
7. [Organization System](#organization-system)
8. [Desktop UI](#desktop-ui)
9. [Configuration](#configuration)
10. [API Reference](#api-reference)
11. [Running the Application](#running-the-application)

---

## Project Overview

### What is Mac Assistant?

Mac Assistant is a **100% local** AI desktop assistant for macOS that combines:

- **On-device AI inference** via Microsoft Foundry Local SDK
- **RAG (Retrieval-Augmented Generation)** with specialized knowledge pockets
- **Persistent chat history** with SQLite storage
- **Project-based organization** with folders and tags
- **Native desktop UI** built with Electron
- **Real-time streaming** responses with performance metrics
- **Model management** with download, switch, and cache management

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **100% Local** | No cloud dependencies - all AI inference happens on-device |
| **Privacy First** | All data stored locally in SQLite, no telemetry |
| **Modular Architecture** | Separate concerns: API, RAG, Storage, UI |
| **Performance Visibility** | Real-time tokens/second monitoring |
| **Extensible RAG** | Pluggable "pockets" for domain-specific knowledge |
| **Organized Workflows** | Projects, folders, and tags for chat organization |

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
│  │  - Messages  │  │  - Projects  │  │  - Model     │           │
│  │  - Streaming │  │  - Folders   │  │  - Theme     │           │
│  │  - Metrics   │  │  - Tags      │  │  - Params    │           │
│  │  - Sources   │  │  - Sessions  │  │  - Downloads │           │
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
│  │  /chat  /models  /organize  /rag  /export  /projects    │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│  ┌─────────────┬───────────┼───────────┬─────────────┐          │
│  │             │           │           │             │          │
│  ▼             ▼           ▼           ▼             ▼          │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐         │
│ │Foundry │ │  RAG   │ │Storage │ │Organize│ │Projects│         │
│ │Manager │ │Retriever│ │ Layer │ │ Repo   │ │  Repo  │         │
│ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘         │
│     │          │          │          │          │               │
│     │     ┌────┴────┐     │          │          │               │
│     │     │         │     │          │          │               │
│     │     ▼         ▼     ▼          ▼          ▼               │
│     │  ┌──────┐ ┌──────┐ ┌────────────────────────┐             │
│     │  │Qdrant│ │Embed │ │     SQLite Database    │             │
│     │  │Vector│ │Model │ │  - chat_sessions       │             │
│     │  │Store │ │      │ │  - chat_messages       │             │
│     │  └──────┘ └──────┘ │  - chat_folders        │             │
│     │                    │  - chat_tags           │             │
│     │                    │  - projects            │             │
│     │                    │  - folder_watchers     │             │
│     │                    │  - documents           │             │
│     │                    │  - settings            │             │
│     │                    └────────────────────────┘             │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              FOUNDRY LOCAL SDK                            │   │
│  │  - OpenAI-compatible API                                  │   │
│  │  - On-device inference (Apple Silicon optimized)          │   │
│  │  - Model management (download/load/unload/switch)         │   │
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
│   ├── __init__.py              # Version: 1.1.0
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
│   │   ├── folders.py           # FolderRepository (folders + tags)
│   │   ├── projects.py          # ProjectRepository
│   │   ├── watchers.py          # WatcherRepository (folder watchers)
│   │   ├── documents.py         # DocumentRepository
│   │   ├── settings.py          # SettingsRepository
│   │   └── export.py            # ExportService (backup/restore)
│   │
│   ├── services/                # Background services
│   │   └── watcher.py           # Folder watcher service
│   │
│   ├── api/                     # FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app factory, lifespan
│   │   ├── websocket.py         # WebSocket endpoints
│   │   └── routes/              # API route modules
│   │       ├── __init__.py
│   │       ├── chat.py          # /chat endpoints
│   │       ├── models.py        # /models endpoints
│   │       ├── folders.py       # /organize endpoints (folders, tags)
│   │       ├── projects.py      # /projects endpoints
│   │       ├── watchers.py      # /watchers endpoints
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
│           ├── app.js           # Frontend application logic
│           └── quick-prompt.html # Quick prompt window
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
| `models_router` | `/models` | Model management (download, switch, delete) |
| `folders_router` | `/organize` | Folders and tags management |
| `projects_router` | `/projects` | Project management |
| `watchers_router` | `/watchers` | Folder watcher configuration |
| `settings_router` | `/settings` | Application settings |
| `rag_router` | `/rag` | RAG operations |
| `export_router` | `/export` | Data export/import |
| `speech_router` | `/speech` | Speech-to-text (Whisper) |
| `websocket_router` | `/ws` | WebSocket endpoints |

---

## Organization System

### Overview

Mac Assistant includes a comprehensive organization system for managing chats:

1. **Projects** - High-level workspaces that group related work
2. **Folders** - Collapsible containers within projects for organizing chats
3. **Tags** - Cross-cutting labels that can be applied to any chat

### Projects

Projects are top-level organizational units that allow users to separate different work contexts:

| Feature | Description |
|---------|-------------|
| **Isolation** | Each project has its own chats and folders |
| **Default Pocket** | Projects can have an associated RAG pocket |
| **System Prompt** | Custom AI instructions per project |
| **Color Coding** | Visual identification in the UI |
| **All Chats View** | Special view showing chats across all projects |

### Folders

Folders are collapsible containers that organize chats within a project:

| Feature | Description |
|---------|-------------|
| **Collapsible** | Click to expand/collapse and show nested chats |
| **Project Assignment** | Folders can belong to a specific project or be global |
| **Session Count** | Shows number of chats in each folder |
| **Inheritance** | Chats moved to a folder inherit the folder's project |
| **Context Menu** | Right-click for folder actions |

### Tags

Tags provide cross-cutting categorization:

| Feature | Description |
|---------|-------------|
| **Color Coded** | Each tag has a customizable color |
| **Filter by Tag** | Click a tag to filter the chat list |
| **Multiple Tags** | Chats can have multiple tags |
| **Global** | Tags work across all projects |

### Data Relationships

```
Project (optional)
    │
    ├── Folder (inherits project_id)
    │       │
    │       └── Chat Session (inherits folder's project_id)
    │               │
    │               └── Tags (many-to-many)
    │
    └── Chat Session (direct project assignment)
            │
            └── Tags (many-to-many)
```

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
    folder_id VARCHAR(36) REFERENCES chat_folders(id),
    project_id VARCHAR(36) REFERENCES projects(id),
    is_archived BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
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

-- Chat Folders
CREATE TABLE chat_folders (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(7) DEFAULT '#808080',
    icon VARCHAR(50) DEFAULT 'folder',
    parent_id VARCHAR(36) REFERENCES chat_folders(id),
    project_id VARCHAR(36) REFERENCES projects(id),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat Tags
CREATE TABLE chat_tags (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    color VARCHAR(7) DEFAULT '#007AFF',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Session-Tag Association (many-to-many)
CREATE TABLE chat_session_tags (
    session_id VARCHAR(36) REFERENCES chat_sessions(id),
    tag_id VARCHAR(36) REFERENCES chat_tags(id),
    PRIMARY KEY (session_id, tag_id)
);

-- Projects
CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7) DEFAULT '#007AFF',
    icon VARCHAR(50) DEFAULT 'folder',
    default_pocket VARCHAR(50),
    system_prompt TEXT,
    is_archived BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Folder Watchers (auto-ingest from filesystem)
CREATE TABLE folder_watchers (
    id VARCHAR(36) PRIMARY KEY,
    pocket_id VARCHAR(50) NOT NULL,
    folder_path TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    watch_subdirs BOOLEAN DEFAULT TRUE,
    file_patterns TEXT DEFAULT '*.pdf,*.txt,*.md',
    last_scan TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
| `FolderRepository` | Folder and tag management, session organization |
| `ProjectRepository` | Project CRUD with session counts |
| `WatcherRepository` | Folder watcher configuration |
| `DocumentRepository` | Document metadata tracking |
| `SettingsRepository` | Key-value settings with type coercion |
| `ExportService` | Full/partial data export and import |

### Database Location

```
~/.mac-assistant/
├── assistant.db          # SQLite database
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
| Sidebar | `index.html` | Projects, folders, tags, session list |
| Chat Area | `index.html` | Messages, streaming, metrics |
| Input Area | `index.html` | Textarea with send/stop buttons |
| Settings Modal | `index.html` | Configuration options |
| Model Manager | `index.html` | Download, switch, delete models |
| Move to Folder Modal | `index.html` | Organize chats into folders |
| Move to Project Modal | `index.html` | Assign chats to projects |
| Create Folder Modal | `index.html` | New folder creation |
| Create Tag Modal | `index.html` | New tag creation |
| Create Project Modal | `index.html` | New project creation |
| Context Menus | `index.html` | Right-click menus for sessions/folders |

### Sidebar Organization

The sidebar is organized into sections:

1. **RAG Pocket Selector** - Choose knowledge context
2. **Project Switcher** - Switch between projects or "All Chats"
3. **Folders Section** - Collapsible folders with nested chats
4. **Tags Section** - Filterable tags
5. **Recent Chats** - Root-level chats (not in folders)

### Chat Features

- **Stop Generation**: Red stop button appears during AI response generation
- **Message Input**: Enter sends message, Shift+Enter adds new line
- **Streaming**: Real-time token display with performance metrics
- **Context Menu**: Right-click chats for organization options
- **Pin Chats**: Pin important chats to the top
- **Archive**: Archive old chats without deleting

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
| `Cmd+N` | New chat |
| `Cmd+M` | Toggle metrics panel |
| `Cmd+\` | Toggle sidebar |
| `Cmd+,` | Open settings |
| `Cmd+E` | Export data |
| `Cmd+I` | Import data |
| `Enter` | Send message |
| `Shift+Enter` | New line in message |

### Menu Bar

```
Mac Assistant
├── About Mac Assistant
├── Preferences... (Cmd+,)
├── Services
├── Hide/Quit

File
├── New Chat (Cmd+N)
├── Export Data... (Cmd+E)
├── Import Data... (Cmd+I)
├── Close Window

Edit
├── Undo/Redo
├── Cut/Copy/Paste
├── Select All

View
├── Toggle Sidebar (Cmd+\)
├── Toggle Metrics (Cmd+M)
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
  "sources": [...],
  "metrics": {
    "tokens_generated": 150,
    "tokens_per_second": 45.2,
    "total_time": 3.32
  }
}
```

#### `POST /chat/stream`
Stream response via Server-Sent Events.

#### `GET /chat/sessions`
List chat sessions with optional filtering.

**Query Parameters:**
- `project_id`: Filter by project
- `folder_id`: Filter by folder
- `tag_id`: Filter by tag
- `rag_pocket`: Filter by pocket
- `pinned_only`: Only pinned sessions
- `include_archived`: Include archived
- `limit`: Max results (default 50)
- `offset`: Pagination offset

#### `PATCH /chat/sessions/{session_id}`
Update session properties (title, archive status, project).

### Organization Endpoints

#### Folders

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/organize/folders` | GET | List folders (with project filtering) |
| `/organize/folders` | POST | Create a new folder |
| `/organize/folders/{id}` | GET | Get folder details |
| `/organize/folders/{id}` | PUT | Update folder |
| `/organize/folders/{id}` | DELETE | Delete folder |
| `/organize/folders/{id}/project` | PUT | Assign folder to project |
| `/organize/sessions/{id}/folder` | PUT | Move session to folder |

#### Tags

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/organize/tags` | GET | List all tags |
| `/organize/tags` | POST | Create a new tag |
| `/organize/tags/{id}` | PUT | Update tag |
| `/organize/tags/{id}` | DELETE | Delete tag |
| `/organize/sessions/{id}/tags` | GET | Get session's tags |
| `/organize/sessions/{id}/tags` | PUT | Set session's tags |
| `/organize/sessions/{id}/tags/{tag_id}` | POST | Add tag to session |
| `/organize/sessions/{id}/tags/{tag_id}` | DELETE | Remove tag from session |

#### Sessions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/organize/sessions/{id}/pin` | PUT | Pin/unpin session |
| `/organize/sessions/{id}/archive` | PUT | Archive/unarchive session |

### Project Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects` | GET | List all projects (with session counts) |
| `/projects` | POST | Create a new project |
| `/projects/{id}` | GET | Get project details |
| `/projects/{id}` | PUT | Update project |
| `/projects/{id}` | DELETE | Delete project |

### Model Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/models` | GET | Get current model info |
| `/models/available` | GET | List all available models |
| `/models/loaded` | GET | List currently loaded models |
| `/models/cached` | GET | List cached (downloaded) models |
| `/models/switch` | POST | Switch to a different model |
| `/models/unload` | POST | Unload a model from memory |
| `/models/download/{alias}` | POST | Download a model (async) |
| `/models/downloads/{alias}/status` | GET | Get download progress |
| `/models/cache/{alias}` | DELETE | Delete a cached model |

### Health & Metrics

#### `GET /health`
```json
{
  "status": "healthy",
  "foundry_running": true,
  "current_model": "qwen2.5-1.5b-instruct",
  "qdrant_status": "not_initialized",
  "version": "1.1.0"
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
| `phi-4-mini` | 3.8B | Latest Phi model |
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

*Documentation generated for Mac Assistant v1.1.0*
