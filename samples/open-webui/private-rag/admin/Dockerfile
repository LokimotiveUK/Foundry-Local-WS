# Private RAG Document Manager
# Lightweight Streamlit-based admin UI

FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck and upgrade pip
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip

# Install Python dependencies
RUN pip install --no-cache-dir \
    streamlit>=1.31.0 \
    qdrant-client>=1.7.0 \
    requests>=2.31.0

# Copy app
COPY app.py .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
