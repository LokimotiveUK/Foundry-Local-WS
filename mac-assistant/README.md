# Mac Desktop AI Assistant

A fully local AI desktop assistant for macOS with RAG (Retrieval-Augmented Generation) capabilities. Built on Microsoft Foundry Local for on-device inference.

## Features

- **100% Local**: All processing happens on your Mac - no cloud dependencies
- **RAG Pockets**: Specialized knowledge bases for different domains (medical, finance, study, writing)
- **Model Switching**: Hot-swap between different AI models
- **Verbose Mode**: Real-time tokens/second monitoring
- **Chat History**: Persistent conversation storage
- **Adjustable Context**: Configure context window size per conversation

## Requirements

- macOS 12+ (Apple Silicon recommended)
- Python 3.10+
- [Foundry Local](https://github.com/microsoft/Foundry-Local) installed via Homebrew:
  ```bash
  brew install microsoft/foundrylocal/foundrylocal
  ```

## Quick Start

### 1. Install Backend Dependencies

```bash
cd mac-assistant
pip install -e .
```

### 2. Download a Model

```bash
foundry model download qwen2.5-1.5b-instruct
```

### 3. Start the Backend

```bash
python -m src.api.main
```

The API will be available at `http://localhost:8000`

### 4. Install & Run Desktop UI

```bash
cd desktop/electron
npm install
npm start
```

Or use the combined launcher script:

```bash
./start.sh
```

### 4. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send a message and get a response |
| `/chat/stream` | POST | Stream a response (SSE) |
| `/ws/chat` | WebSocket | Real-time bidirectional chat |
| `/models` | GET | List available models |
| `/models/switch` | POST | Switch to a different model |
| `/models/current` | GET | Get current model info |
| `/metrics` | GET | Get performance metrics |
| `/settings` | GET/PUT | Manage settings |
| `/rag/pockets` | GET/POST | List/create RAG pockets |
| `/rag/pockets/{id}/documents/upload` | POST | Upload documents |
| `/rag/ingest` | POST | Ingest documents to vector DB |
| `/rag/query` | POST | RAG query with AI response |
| `/rag/search` | POST | Semantic search only |
| `/rag/stats` | GET | RAG system statistics |

## RAG Pockets

Organize your documents into specialized knowledge bases:

```
data/pockets/
├── medical/     # Medical records, lab results
├── finance/     # Bank statements, tax docs
├── study/       # Textbooks, research papers
└── writing/     # Manuscripts, references
```

### Adding Documents

1. **Upload via API**:
   ```bash
   curl -X POST http://localhost:8000/rag/pockets/medical/documents/upload \
     -F "file=@lab_results.pdf"
   ```

2. **Copy to pocket folder**:
   ```bash
   cp ~/Documents/medical/*.pdf mac-assistant/data/pockets/medical/
   ```

3. **Ingest all documents**:
   ```bash
   curl -X POST http://localhost:8000/rag/ingest \
     -H "Content-Type: application/json" \
     -d '{"pocket_id": "medical"}'
   ```

### Querying with RAG

```bash
# Query with RAG context
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What were my cholesterol levels?",
    "rag_pocket": "medical"
  }'

# Semantic search only (no AI response)
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "cholesterol",
    "pocket_id": "medical"
  }'
```

### Custom Pockets

Create your own specialized pockets:

```bash
curl -X POST http://localhost:8000/rag/pockets \
  -H "Content-Type: application/json" \
  -d '{
    "id": "recipes",
    "name": "Recipes",
    "description": "Cooking recipes and meal plans",
    "system_prompt": "You are a cooking assistant...",
    "chunk_size": 300
  }'
```

## Configuration

Settings are stored in `~/.mac-assistant/config.json`:

```json
{
  "default_model": "qwen2.5-1.5b-instruct",
  "context_window": 4096,
  "verbose_mode": true,
  "embedding_model": "all-MiniLM-L6-v2"
}
```

## Desktop UI

The desktop UI is built with Electron and provides a native-feeling chat interface.

### Features

- **Modern Chat Interface**: Clean, responsive design with dark/light themes
- **RAG Pocket Selector**: Switch between knowledge bases from the sidebar
- **Real-time Streaming**: See responses appear token-by-token
- **Metrics Display**: Monitor tokens/second, response time, and token count
- **Session Management**: Browse and resume previous conversations
- **Source Citations**: View RAG sources used for each response
- **Keyboard Shortcuts**:
  - `⌘N` - New chat
  - `⌘M` - Toggle metrics panel
  - `⌘\` - Toggle sidebar
  - `⌘,` - Open settings
  - `⌘Enter` - Send message

### Running the Desktop UI

```bash
# Install dependencies
cd desktop/electron
npm install

# Run in development mode
npm run dev

# Run in production mode
npm start

# Build distributable
npm run build:mac
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              Desktop UI (Electron)          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │  Chat   │  │ Session │  │Settings │     │
│  │  View   │  │ Sidebar │  │ Panel   │     │
│  └────┬────┘  └────┬────┘  └────┬────┘     │
└───────┼────────────┼────────────┼───────────┘
        │            │            │
        ▼            ▼            ▼
┌─────────────────────────────────────────────┐
│           FastAPI Backend                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │  Chat   │  │  RAG    │  │ Models  │     │
│  │ Routes  │  │ Engine  │  │ Manager │     │
│  └────┬────┘  └────┬────┘  └────┬────┘     │
│       │            │            │           │
│  ┌────┴────────────┴────────────┴────┐     │
│  │         SQLite Storage            │     │
│  │  (Sessions, Messages, Settings)   │     │
│  └───────────────────────────────────┘     │
│       │            │            │           │
│       ▼            ▼            ▼           │
│  ┌─────────────────────────────────────┐   │
│  │      Foundry Local SDK              │   │
│  │   (On-device AI inference)          │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Development

```bash
# Run tests
pytest tests/

# Run with auto-reload
uvicorn src.api.main:app --reload

# Format code
ruff format src/
```

## License

MIT License - See LICENSE file
