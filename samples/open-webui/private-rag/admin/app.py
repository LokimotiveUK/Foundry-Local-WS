"""
Private RAG Document Manager

A Streamlit-based admin interface for managing RAG documents.
- Upload new documents (PDF, TXT, MD, DOCX)
- View indexed documents
- Delete documents from the vector store
- Re-index all documents
- View collection statistics
"""

import hashlib
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

# Ensure directories exist
HEALTHCARE_DIR = DOCUMENTS_DIR / "healthcare"
FINANCE_DIR = DOCUMENTS_DIR / "finance"
HEALTHCARE_DIR.mkdir(parents=True, exist_ok=True)
FINANCE_DIR.mkdir(parents=True, exist_ok=True)

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
        # Scroll through all points to get unique documents
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


def get_local_files():
    """Get list of files in the documents directory."""
    files = []
    for category_dir in [HEALTHCARE_DIR, FINANCE_DIR]:
        category = category_dir.name
        for f in category_dir.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                files.append({
                    "name": f.name,
                    "path": str(f.relative_to(DOCUMENTS_DIR.parent)),
                    "category": category,
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


# Main UI
st.title("📁 Private RAG Document Manager")
st.markdown("Manage your healthcare and finance documents for local AI search.")

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

# Main content tabs
tab1, tab2, tab3 = st.tabs(["📤 Upload", "📋 Indexed Documents", "📁 Local Files"])

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
        category = st.selectbox(
            "Category",
            ["healthcare", "finance"],
            help="Where to store the documents"
        )

    if uploaded_files:
        st.write(f"**{len(uploaded_files)} file(s) selected:**")
        for f in uploaded_files:
            st.write(f"- {f.name} ({f.size:,} bytes)")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Save Files", type="primary", use_container_width=True):
                target_dir = HEALTHCARE_DIR if category == "healthcare" else FINANCE_DIR
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
                target_dir = HEALTHCARE_DIR if category == "healthcare" else FINANCE_DIR
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
        healthcare_docs = [d for d in indexed_docs if d["category"] == "healthcare"]
        finance_docs = [d for d in indexed_docs if d["category"] == "finance"]

        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"🏥 Healthcare ({len(healthcare_docs)})")
            for doc in healthcare_docs:
                with st.container():
                    cols = st.columns([4, 1, 1])
                    cols[0].write(f"**{doc['name']}**")
                    cols[1].write(f"{doc['chunks']} chunks")
                    if cols[2].button("🗑️", key=f"del_{doc['path']}", help="Delete from index"):
                        if delete_document_vectors(doc["path"]):
                            st.success(f"Removed {doc['name']} from index")
                            st.rerun()

        with col2:
            st.subheader(f"💰 Finance ({len(finance_docs)})")
            for doc in finance_docs:
                with st.container():
                    cols = st.columns([4, 1, 1])
                    cols[0].write(f"**{doc['name']}**")
                    cols[1].write(f"{doc['chunks']} chunks")
                    if cols[2].button("🗑️", key=f"del_{doc['path']}", help="Delete from index"):
                        if delete_document_vectors(doc["path"]):
                            st.success(f"Removed {doc['name']} from index")
                            st.rerun()

# Tab 3: Local Files
with tab3:
    st.header("Local Files")
    st.caption("Files in the documents folder (may or may not be indexed)")

    local_files = get_local_files()

    if not local_files:
        st.info("No files in documents folder. Upload some documents!")
    else:
        col1, col2 = st.columns(2)

        healthcare_files = [f for f in local_files if f["category"] == "healthcare"]
        finance_files = [f for f in local_files if f["category"] == "finance"]

        with col1:
            st.subheader(f"🏥 Healthcare ({len(healthcare_files)})")
            for f in healthcare_files:
                with st.container():
                    cols = st.columns([4, 2, 1])
                    cols[0].write(f"**{f['name']}**")
                    cols[1].write(f"{f['size']:,} bytes")
                    if cols[2].button("🗑️", key=f"file_{f['path']}", help="Delete file"):
                        file_path = DOCUMENTS_DIR.parent / f["path"]
                        if file_path.exists():
                            file_path.unlink()
                            # Also remove from index
                            delete_document_vectors(f["path"])
                            st.success(f"Deleted {f['name']}")
                            st.rerun()

        with col2:
            st.subheader(f"💰 Finance ({len(finance_files)})")
            for f in finance_files:
                with st.container():
                    cols = st.columns([4, 2, 1])
                    cols[0].write(f"**{f['name']}**")
                    cols[1].write(f"{f['size']:,} bytes")
                    if cols[2].button("🗑️", key=f"file_{f['path']}", help="Delete file"):
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

# Footer
st.divider()
st.caption("All data stays on your device. No cloud services used.")
