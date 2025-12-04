# Open WebUI Tools for Private RAG

Category-specific tools that connect Open WebUI workspaces to your private document RAG system.

## Available Tools

| Tool File | Category | Use Case |
|-----------|----------|----------|
| `job_search_tool.py` | job-search | Resumes, cover letters, job applications |
| `healthcare_tool.py` | healthcare | Medical records, lab results, prescriptions |
| `finance_tool.py` | finance | Bank statements, tax returns, investments |

## Setup Instructions

### Prerequisites
- Foundry Local service running (`foundry service start`)
- Private RAG containers running (`docker compose up -d` in `private-rag/`)
- Documents uploaded and ingested via Admin UI (http://localhost:8501)

### Step 1: Create the Tool in Open WebUI

1. Open **http://localhost:3000**
2. Go to **Workspace** > **Tools**
3. Click **+** (Create Tool)
4. Copy the entire contents of the tool file (e.g., `job_search_tool.py`)
5. Paste into the code editor
6. Click **Save**

### Step 2: Create a Custom Model with Tool Support

1. Go to **Workspace** > **Models**
2. Click **+** to create a new model
3. Configure:
   - **Name**: "Job Search Assistant" (or similar)
   - **Base Model**: Select your Foundry Local model (e.g., phi-3.5-mini)
   - **System Prompt**: Use the recommended prompt below
   - **Tools**: Enable the Job Search RAG tool

4. **CRITICAL - Configure Function Calling**:
   - Scroll to **Advanced Params**
   - Find **Function Calling** setting
   - Set to **"Default"** (NOT "Native")

   > **Why Default Mode?** Phi-3.5-mini and many local models don't support native function calling. Default Mode uses prompt engineering to guide the model to use tools, which works with any model.

5. Click **Save**

### Recommended System Prompt

Use this system prompt for reliable tool calling:

```
You are a helpful assistant with access to the user's personal documents.

IMPORTANT: You have access to a document search tool. You MUST use this tool to answer questions about the user's documents.

When the user asks about their resume, CV, cover letters, job applications, skills, or work experience:
1. ALWAYS call the search_job_documents tool first
2. Use the returned information to provide a helpful response
3. Never make up information - only use what the tool returns

Do not ask the user to provide or paste their documents - you can search their uploaded documents directly using the tool.
```

### Step 3: Use the Custom Model

1. Start a **New Chat**
2. Select your custom model (e.g., "Job Search Assistant")
3. Ask questions about your documents

## Example Queries

### Job Search Tool
- "Review my resume and suggest improvements"
- "What skills are highlighted in my CV?"
- "Help me tailor my resume for a Senior Developer position"

### Healthcare Tool
- "What were my cholesterol levels in my last blood test?"
- "List my current medications"
- "Summarize my recent doctor visits"

### Finance Tool
- "What was my total income last year?"
- "What tax deductions did I claim?"
- "Summarize my investment portfolio"

## Creating Tools for New Categories

When you create a new category in the RAG Admin UI, you can create a matching tool:

1. Copy one of the existing tool files
2. Update the `title` and `description` in the docstring
3. Change `self.category = "your-category-name"`
4. Update the method names and docstrings to match your use case
5. Register in Open WebUI

## Troubleshooting

### Model doesn't call the tool (most common issue)

If the model gives generic advice instead of searching your documents:

1. **Check Function Calling Mode**:
   - Go to **Workspace** > **Models** > Edit your model
   - Scroll to **Advanced Params**
   - Ensure **Function Calling** is set to **"Default"** (not "Native")
   - Phi-3.5-mini does NOT support native function calling

2. **Add/Update the System Prompt**:
   - Make sure your model has a system prompt that explicitly tells it to use the tool
   - See "Recommended System Prompt" section above

3. **Check Tool is Enabled**:
   - In the model settings, verify the tool is checked/enabled
   - The tool toggle should be ON (green)

4. **Verify Foundry Local is Running**:
   ```powershell
   foundry service status
   # If not running:
   foundry service start
   ```

5. **Try a More Explicit Query**:
   - Instead of "Give me feedback on my resume"
   - Try "Search my documents and give me feedback on my resume"

### "Cannot connect to RAG server"
```powershell
# Check if containers are running
docker ps | grep rag

# Start containers if needed
cd samples/open-webui/private-rag
docker compose up -d
```

### Tool not appearing in model settings
- Make sure you saved the tool after pasting
- Refresh the Open WebUI page
- Go back to Workspace > Tools and verify it shows in the list

### No results found
- Verify documents are uploaded in Admin UI (http://localhost:8501)
- Check the "Indexed Documents" tab shows your files
- Re-run ingestion if needed

### "LLM generation failed: Connection error"

This means the RAG server can retrieve documents but can't connect to Foundry Local to generate the response.

1. Make sure Foundry Local is running:
   ```powershell
   foundry service status
   foundry service start  # if needed
   ```

2. Check the RAG server can reach Foundry Local:
   ```powershell
   # From host machine
   curl http://localhost:5273/v1/models

   # If using dynamic port, check service status for the actual port
   ```

3. Restart RAG containers to pick up new Foundry port:
   ```powershell
   cd samples/open-webui/private-rag
   docker compose restart rag-server
   ```
