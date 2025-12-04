"""
Private RAG Document Manager

A Streamlit-based admin interface for managing RAG documents.
- Upload new documents (PDF, TXT, MD, DOCX)
- View indexed documents
- Delete documents from the vector store
- Create and manage custom categories
- Re-index all documents
- View collection statistics
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

import requests
import streamlit as st
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
RAG_SERVER = os.getenv("RAG_SERVER", "http://localhost:8000")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "private_docs")
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR", "/app/documents"))
CATEGORIES_FILE = Path(os.getenv("CATEGORIES_FILE", "/app/categories.json"))

# Default categories
DEFAULT_CATEGORIES = {
    "healthcare": {
        "description": "Medical records, lab results, prescriptions, doctor notes",
        "icon": "🏥",
        "system_prompt": """You are a helpful assistant analyzing personal healthcare documents.
Be precise with medical terminology and dates. If you're unsure about something, say so.
Never provide medical advice - only summarize and explain the documents provided."""
    },
    "finance": {
        "description": "Bank statements, tax returns, investment reports, receipts",
        "icon": "💰",
        "system_prompt": """You are a helpful assistant analyzing personal financial documents.
Be precise with numbers and dates. Always clarify which document a figure comes from.
Never provide financial advice - only summarize and explain the documents provided."""
    }
}

# Common icons for category selection
CATEGORY_ICONS = ["📁", "🏥", "💰", "💼", "🔍", "📚", "🎓", "🏠", "🚗", "✈️", "🍽️", "🛒", "📝", "⚖️", "🔧", "💻"]


def load_categories() -> dict:
    """Load categories from JSON file."""
    if CATEGORIES_FILE.exists():
        try:
            with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CATEGORIES.copy()


def save_categories(categories: dict) -> bool:
    """Save categories to JSON file."""
    try:
        # Ensure we don't save path objects
        save_data = {}
        for name, info in categories.items():
            save_data[name] = {
                "description": info.get("description", ""),
                "icon": info.get("icon", "📁"),
                "system_prompt": info.get("system_prompt", "You are a helpful assistant.")
            }
        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        st.error(f"Failed to save categories: {e}")
        return False


def ensure_category_dirs(categories: dict):
    """Ensure all category directories exist."""
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    for name in categories:
        (DOCUMENTS_DIR / name).mkdir(exist_ok=True)


# Page config
st.set_page_config(
    page_title="Private RAG Manager",
    page_icon="📁",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stAlert {margin-top: 1rem;}
    .document-card {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #ddd;
        margin-bottom: 0.5rem;
    }
    .stat-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        color: white;
        text-align: center;
    }
    .stat-number {
        font-size: 2.5rem;
        font-weight: bold;
    }
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .category-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        background: #fafafa;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_qdrant_client():
    """Get Qdrant client connection."""
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def get_collection_stats():
    """Get statistics about the vector collection."""
    try:
        client = get_qdrant_client()
        info = client.get_collection(COLLECTION_NAME)
        return {
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.name
        }
    except Exception as e:
        return {"error": str(e)}


def get_indexed_documents():
    """Get list of unique documents in the collection."""
    try:
        client = get_qdrant_client()
        documents = {}
        offset = None

        while True:
            results, offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            for point in results:
                doc_path = point.payload.get("document_path", "")
                doc_name = point.payload.get("document", "")
                category = point.payload.get("category", "general")

                if doc_path not in documents:
                    documents[doc_path] = {
                        "name": doc_name,
                        "path": doc_path,
                        "category": category,
                        "chunks": 0
                    }
                documents[doc_path]["chunks"] += 1

            if offset is None:
                break

        return list(documents.values())
    except Exception as e:
        st.error(f"Error fetching documents: {e}")
        return []


def delete_document_vectors(doc_path: str):
    """Delete all vectors for a specific document."""
    try:
        client = get_qdrant_client()
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(
                    key="document_path",
                    match=MatchValue(value=doc_path)
                )]
            )
        )
        return True
    except Exception as e:
        st.error(f"Error deleting vectors: {e}")
        return False


def delete_all_vectors():
    """Delete all vectors in the collection."""
    try:
        client = get_qdrant_client()
        client.delete_collection(COLLECTION_NAME)
        # Recreate empty collection
        from qdrant_client.models import Distance, VectorParams
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        return True
    except Exception as e:
        st.error(f"Error clearing collection: {e}")
        return False


def get_local_files(categories: dict):
    """Get list of files in the documents directory."""
    files = []
    for category_name in categories:
        category_dir = DOCUMENTS_DIR / category_name
        if category_dir.exists():
            for f in category_dir.iterdir():
                if f.is_file() and not f.name.startswith('.'):
                    files.append({
                        "name": f.name,
                        "path": str(f.relative_to(DOCUMENTS_DIR.parent)),
                        "category": category_name,
                        "size": f.stat().st_size,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime)
                    })
    return files


def trigger_ingestion():
    """Trigger document ingestion via RAG server."""
    try:
        response = requests.post(f"{RAG_SERVER}/ingest", timeout=300)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error triggering ingestion: {e}")
        return False


# Load categories
categories = load_categories()
ensure_category_dirs(categories)

# Main UI
st.title("📁 Private RAG Document Manager")
st.markdown("Manage your private documents for local AI search.")

# Sidebar - Stats
with st.sidebar:
    st.header("📊 Collection Stats")
    stats = get_collection_stats()

    if "error" not in stats:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Vectors", stats.get("vectors_count", 0))
        with col2:
            st.metric("Status", stats.get("status", "Unknown"))
    else:
        st.warning(f"Collection not found. Run ingestion first.")

    st.divider()

    # Quick actions
    st.header("⚡ Quick Actions")

    if st.button("🔄 Refresh Stats", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    if st.button("🗑️ Clear All Vectors", use_container_width=True, type="secondary"):
        if st.session_state.get("confirm_clear"):
            if delete_all_vectors():
                st.success("All vectors cleared!")
                st.session_state.confirm_clear = False
                st.rerun()
        else:
            st.session_state.confirm_clear = True
            st.warning("Click again to confirm deletion")

    st.divider()

    # Categories summary
    st.header("📂 Categories")
    for name, info in categories.items():
        icon = info.get("icon", "📁")
        st.write(f"{icon} **{name}**")

# Main content tabs
tab1, tab2, tab3, tab4 = st.tabs(["📤 Upload", "📋 Indexed Documents", "📁 Local Files", "⚙️ Categories"])

# Tab 1: Upload
with tab1:
    st.header("Upload New Documents")

    col1, col2 = st.columns([3, 1])

    with col1:
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=["pdf", "txt", "md", "docx"],
            accept_multiple_files=True,
            help="Supported formats: PDF, TXT, Markdown, Word documents"
        )

    with col2:
        category_names = list(categories.keys())
        category = st.selectbox(
            "Category",
            category_names,
            help="Where to store the documents"
        )

    if uploaded_files:
        st.write(f"**{len(uploaded_files)} file(s) selected:**")
        for f in uploaded_files:
            st.write(f"- {f.name} ({f.size:,} bytes)")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Save Files", type="primary", use_container_width=True):
                target_dir = DOCUMENTS_DIR / category
                target_dir.mkdir(exist_ok=True)
                saved = 0
                for uploaded_file in uploaded_files:
                    file_path = target_dir / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved += 1
                st.success(f"Saved {saved} file(s) to {category}/")
                st.info("Run ingestion to index the new documents.")

        with col2:
            if st.button("💾 Save & Ingest", use_container_width=True):
                target_dir = DOCUMENTS_DIR / category
                target_dir.mkdir(exist_ok=True)
                saved = 0
                for uploaded_file in uploaded_files:
                    file_path = target_dir / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    saved += 1
                st.success(f"Saved {saved} file(s)")
                with st.spinner("Indexing documents..."):
                    if trigger_ingestion():
                        st.success("Documents indexed successfully!")
                    else:
                        st.warning("Auto-ingestion failed. Run manually: python ingest.py")

# Tab 2: Indexed Documents
with tab2:
    st.header("Indexed Documents")
    st.caption("Documents currently searchable in the RAG system")

    indexed_docs = get_indexed_documents()

    if not indexed_docs:
        st.info("No documents indexed yet. Upload files and run ingestion.")
    else:
        # Group by category
        docs_by_category = {}
        for doc in indexed_docs:
            cat = doc["category"]
            if cat not in docs_by_category:
                docs_by_category[cat] = []
            docs_by_category[cat].append(doc)

        # Create columns based on number of categories (max 3 per row)
        cat_names = list(docs_by_category.keys())
        num_cols = min(len(cat_names), 3)
        cols = st.columns(num_cols) if num_cols > 0 else [st]

        for i, cat_name in enumerate(cat_names):
            cat_info = categories.get(cat_name, {"icon": "📁"})
            icon = cat_info.get("icon", "📁")
            docs = docs_by_category[cat_name]

            with cols[i % num_cols]:
                st.subheader(f"{icon} {cat_name.title()} ({len(docs)})")
                for doc in docs:
                    with st.container():
                        doc_cols = st.columns([4, 1, 1])
                        doc_cols[0].write(f"**{doc['name']}**")
                        doc_cols[1].write(f"{doc['chunks']} chunks")
                        if doc_cols[2].button("🗑️", key=f"del_{doc['path']}", help="Delete from index"):
                            if delete_document_vectors(doc["path"]):
                                st.success(f"Removed {doc['name']} from index")
                                st.rerun()

# Tab 3: Local Files
with tab3:
    st.header("Local Files")
    st.caption("Files in the documents folder (may or may not be indexed)")

    local_files = get_local_files(categories)

    if not local_files:
        st.info("No files in documents folder. Upload some documents!")
    else:
        # Group by category
        files_by_category = {}
        for f in local_files:
            cat = f["category"]
            if cat not in files_by_category:
                files_by_category[cat] = []
            files_by_category[cat].append(f)

        cat_names = list(files_by_category.keys())
        num_cols = min(len(cat_names), 3)
        cols = st.columns(num_cols) if num_cols > 0 else [st]

        for i, cat_name in enumerate(cat_names):
            cat_info = categories.get(cat_name, {"icon": "📁"})
            icon = cat_info.get("icon", "📁")
            files = files_by_category[cat_name]

            with cols[i % num_cols]:
                st.subheader(f"{icon} {cat_name.title()} ({len(files)})")
                for f in files:
                    with st.container():
                        file_cols = st.columns([4, 2, 1])
                        file_cols[0].write(f"**{f['name']}**")
                        file_cols[1].write(f"{f['size']:,} bytes")
                        if file_cols[2].button("🗑️", key=f"file_{f['path']}", help="Delete file"):
                            file_path = DOCUMENTS_DIR.parent / f["path"]
                            if file_path.exists():
                                file_path.unlink()
                                delete_document_vectors(f["path"])
                                st.success(f"Deleted {f['name']}")
                                st.rerun()

    st.divider()

    # Manual ingestion button
    if st.button("🔄 Re-index All Documents", type="primary"):
        with st.spinner("Indexing all documents..."):
            if trigger_ingestion():
                st.success("All documents re-indexed!")
                st.rerun()
            else:
                st.error("Ingestion failed. Check RAG server logs.")

# Tab 4: Categories
with tab4:
    st.header("⚙️ Manage Categories")
    st.caption("Create custom categories for organizing your documents")

    # Add new category
    st.subheader("➕ Add New Category")

    with st.form("new_category_form"):
        col1, col2 = st.columns([3, 1])

        with col1:
            new_name = st.text_input(
                "Category Name",
                placeholder="e.g., job-search, recipes, travel",
                help="Use lowercase letters and hyphens. Spaces will be converted to hyphens."
            )

        with col2:
            new_icon = st.selectbox("Icon", CATEGORY_ICONS, index=0)

        new_description = st.text_input(
            "Description",
            placeholder="e.g., Resumes, cover letters, job applications",
            help="Brief description of what documents this category contains"
        )

        new_prompt = st.text_area(
            "System Prompt (optional)",
            placeholder="Custom instructions for the AI when answering questions about these documents...",
            help="Leave blank for a default prompt"
        )

        submitted = st.form_submit_button("Create Category", type="primary")

        if submitted:
            if not new_name:
                st.error("Please enter a category name")
            else:
                # Normalize name
                normalized_name = new_name.lower().strip().replace(" ", "-").replace("_", "-")

                if normalized_name in categories:
                    st.error(f"Category '{normalized_name}' already exists")
                else:
                    # Create the category
                    if not new_prompt:
                        new_prompt = f"""You are a helpful assistant analyzing personal {normalized_name} documents.
Be precise with details and dates. Always clarify which document information comes from.
Only answer based on the provided context. If the answer isn't in the context, say so."""

                    categories[normalized_name] = {
                        "description": new_description,
                        "icon": new_icon,
                        "system_prompt": new_prompt
                    }

                    # Create directory
                    (DOCUMENTS_DIR / normalized_name).mkdir(exist_ok=True)

                    # Save categories
                    if save_categories(categories):
                        st.success(f"Created category: {new_icon} {normalized_name}")
                        st.rerun()
                    else:
                        st.error("Failed to save category")

    st.divider()

    # Existing categories
    st.subheader("📂 Existing Categories")

    for name, info in categories.items():
        icon = info.get("icon", "📁")
        description = info.get("description", "No description")

        with st.expander(f"{icon} **{name}** - {description}"):
            st.write(f"**Description:** {description}")
            st.write(f"**Directory:** `documents/{name}/`")

            # Show system prompt
            with st.container():
                st.write("**System Prompt:**")
                st.code(info.get("system_prompt", "Default prompt"), language=None)

            # Delete button (only for non-default categories or if empty)
            category_dir = DOCUMENTS_DIR / name
            file_count = len(list(category_dir.glob("*"))) if category_dir.exists() else 0

            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"{file_count} file(s) in this category")

            with col2:
                if file_count == 0:
                    if st.button("🗑️ Delete", key=f"delcat_{name}", type="secondary"):
                        del categories[name]
                        if save_categories(categories):
                            # Remove directory if empty
                            if category_dir.exists():
                                try:
                                    category_dir.rmdir()
                                except OSError:
                                    pass  # Directory not empty
                            st.success(f"Deleted category: {name}")
                            st.rerun()
                else:
                    st.caption("Remove files first")

# Footer
st.divider()
st.caption("All data stays on your device. No cloud services used.")
