"""Chat API routes with RAG integration."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.core.config import Settings, get_settings
from src.core.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    MessageRole,
    MetricsData,
    StreamChunk,
)
from src.foundry.manager import FoundryManager, get_foundry_manager
from src.foundry.metrics import format_metrics
from src.foundry.streaming import StreamingHandler
from src.storage.chats import ChatRepository, get_chat_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_rag_context(
    query: str,
    pocket_id: str,
    settings: Settings,
) -> tuple[str, list[dict[str, Any]]]:
    """Retrieve RAG context for a query.

    Args:
        query: User's query.
        pocket_id: RAG pocket to search.
        settings: Application settings.

    Returns:
        Tuple of (context_string, sources_list).
    """
    try:
        from src.rag.retriever import get_retriever

        retriever = get_retriever()
        retrieval = retriever.retrieve(
            query=query,
            pocket_id=pocket_id,
            top_k=settings.top_k,
            min_score=settings.min_similarity,
        )

        if not retrieval.chunks:
            return "", []

        # Build sources list
        sources = []
        for i, chunk in enumerate(retrieval.chunks):
            sources.append({
                "index": i + 1,
                "document": chunk.document_path.split("/")[-1] if chunk.document_path else "unknown",
                "score": round(chunk.score, 4),
                "text_preview": chunk.text[:150] + "..." if len(chunk.text) > 150 else chunk.text,
            })

        return retrieval.context, sources

    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return "", []


def _build_rag_prompt(query: str, context: str) -> str:
    """Build a RAG-enhanced user prompt.

    Args:
        query: Original user query.
        context: Retrieved context.

    Returns:
        Enhanced prompt with context.
    """
    if not context:
        return query

    return f"""Based on the following context from my documents, please answer my question. If the answer cannot be fully determined from the context, say so and provide what information you can.

Context:
{context}

Question: {query}"""


@router.post("", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    manager: FoundryManager = Depends(get_foundry_manager),
    settings: Settings = Depends(get_settings),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> ChatResponse:
    """Send a chat message and get a response.

    If rag_pocket is specified, relevant context will be retrieved
    from the pocket's documents and included in the prompt.

    This endpoint returns the complete response (non-streaming).
    For streaming responses, use /chat/stream or the WebSocket endpoint.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    # Get or create session from database
    session = chat_repo.get_or_create_session(
        request.session_id,
        manager.current_model or settings.default_model,
        request.rag_pocket,
    )

    # Add user message to database
    chat_repo.add_message(session.id, MessageRole.USER, request.message)

    # Build messages for API
    messages = []
    sources = []

    # Handle RAG pocket
    if request.rag_pocket:
        try:
            from src.rag.pockets import get_pocket_manager

            pocket_manager = get_pocket_manager()
            pocket = pocket_manager.get_pocket(request.rag_pocket)

            # Add system prompt
            messages.append({
                "role": "system",
                "content": pocket.system_prompt,
            })

            # Retrieve context (only for the current message, not history)
            context, sources = _get_rag_context(
                request.message,
                request.rag_pocket,
                settings,
            )

            if context:
                logger.info(f"Retrieved {len(sources)} RAG sources for pocket: {request.rag_pocket}")

        except Exception as e:
            logger.warning(f"RAG pocket error: {e}")
            # Fall back to default system prompt
            from src.core.config import DEFAULT_POCKETS
            pocket_config = DEFAULT_POCKETS.get(request.rag_pocket, {})
            if pocket_config:
                messages.append({
                    "role": "system",
                    "content": pocket_config.get("system_prompt", "You are a helpful assistant."),
                })
            context = ""
    else:
        context = ""

    # Add conversation history if requested
    if request.include_history:
        # Get history from database
        db_messages = chat_repo.get_session_messages(session.id, limit=settings.context_window)
        history_messages = [{"role": m["role"], "content": m["content"]} for m in db_messages]
        # If we have RAG context, enhance the last user message
        if context and history_messages:
            for i in range(len(history_messages) - 1, -1, -1):
                if history_messages[i]["role"] == "user":
                    history_messages[i]["content"] = _build_rag_prompt(
                        history_messages[i]["content"],
                        context,
                    )
                    break
        messages.extend(history_messages)
    else:
        # Single message with potential RAG context
        user_content = _build_rag_prompt(request.message, context) if context else request.message
        messages.append({"role": "user", "content": user_content})

    # Create streaming handler
    model_id = manager.current_model_id
    if not model_id:
        raise HTTPException(status_code=503, detail="No model loaded")

    handler = StreamingHandler(
        client=manager.client,
        model_id=model_id,
        verbose=settings.verbose_mode,
    )

    # Get response
    temperature = request.temperature or settings.temperature
    max_tokens = request.max_tokens or settings.max_response_tokens

    try:
        response_text, metrics = await handler.complete_chat_async(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {e}")

    # Add assistant message to database with metrics
    chat_repo.add_message(
        session.id,
        MessageRole.ASSISTANT,
        response_text,
        metrics=metrics,
        sources=sources if sources else None,
    )

    # Log metrics if verbose
    if settings.verbose_mode and metrics:
        logger.info(f"Response metrics: {format_metrics(metrics)}")

    return ChatResponse(
        message=response_text,
        session_id=session.id,
        model=manager.current_model or "unknown",
        rag_pocket=request.rag_pocket,
        sources=sources,
        metrics=metrics,
    )


@router.post("/stream")
async def stream_message(
    request: ChatRequest,
    manager: FoundryManager = Depends(get_foundry_manager),
    settings: Settings = Depends(get_settings),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> StreamingResponse:
    """Stream a chat response using Server-Sent Events (SSE).

    If rag_pocket is specified, relevant context will be retrieved
    and included in the prompt before streaming begins.

    Each event contains a JSON StreamChunk with content and metrics.
    The final chunk has done=True and complete metrics.
    """
    if not manager.is_initialized:
        raise HTTPException(status_code=503, detail="Foundry not initialized")

    # Get or create session from database
    session = chat_repo.get_or_create_session(
        request.session_id,
        manager.current_model or settings.default_model,
        request.rag_pocket,
    )

    # Add user message to database
    chat_repo.add_message(session.id, MessageRole.USER, request.message)

    # Build messages
    messages = []
    sources = []

    # Handle RAG pocket
    if request.rag_pocket:
        try:
            from src.rag.pockets import get_pocket_manager

            pocket_manager = get_pocket_manager()
            pocket = pocket_manager.get_pocket(request.rag_pocket)

            messages.append({
                "role": "system",
                "content": pocket.system_prompt,
            })

            context, sources = _get_rag_context(
                request.message,
                request.rag_pocket,
                settings,
            )

        except Exception as e:
            logger.warning(f"RAG pocket error: {e}")
            from src.core.config import DEFAULT_POCKETS
            pocket_config = DEFAULT_POCKETS.get(request.rag_pocket, {})
            if pocket_config:
                messages.append({
                    "role": "system",
                    "content": pocket_config.get("system_prompt", "You are a helpful assistant."),
                })
            context = ""
    else:
        context = ""

    # Add history from database
    if request.include_history:
        db_messages = chat_repo.get_session_messages(session.id, limit=settings.context_window)
        history_messages = [{"role": m["role"], "content": m["content"]} for m in db_messages]
        if context and history_messages:
            for i in range(len(history_messages) - 1, -1, -1):
                if history_messages[i]["role"] == "user":
                    history_messages[i]["content"] = _build_rag_prompt(
                        history_messages[i]["content"],
                        context,
                    )
                    break
        messages.extend(history_messages)
    else:
        user_content = _build_rag_prompt(request.message, context) if context else request.message
        messages.append({"role": "user", "content": user_content})

    model_id = manager.current_model_id
    if not model_id:
        raise HTTPException(status_code=503, detail="No model loaded")

    handler = StreamingHandler(
        client=manager.client,
        model_id=model_id,
        verbose=settings.verbose_mode,
    )

    temperature = request.temperature or settings.temperature
    max_tokens = request.max_tokens or settings.max_response_tokens

    async def generate_events():
        """Generate SSE events from stream."""
        full_response = ""
        final_metrics = None

        # Send sources first if available
        if sources:
            sources_event = {"type": "sources", "sources": sources}
            yield f"event: sources\ndata: {json.dumps(sources_event)}\n\n"

        try:
            async for chunk in handler.stream_chat_async(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                full_response += chunk.content

                # Send SSE event
                event_data = chunk.model_dump_json()
                yield f"data: {event_data}\n\n"

                if chunk.done:
                    final_metrics = chunk.metrics
                    # Add assistant message to database with metrics
                    chat_repo.add_message(
                        session.id,
                        MessageRole.ASSISTANT,
                        full_response,
                        metrics=final_metrics,
                        sources=sources if sources else None,
                    )

                    # Send final metadata
                    final_data = {
                        "session_id": session.id,
                        "model": manager.current_model,
                        "rag_pocket": request.rag_pocket,
                        "source_count": len(sources),
                    }
                    yield f"event: metadata\ndata: {json.dumps(final_data)}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            error_data = {"error": str(e)}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_sessions(
    rag_pocket: str | None = None,
    limit: int = 50,
    offset: int = 0,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> list[dict[str, Any]]:
    """List all chat sessions."""
    return chat_repo.list_sessions(limit=limit, offset=offset, rag_pocket=rag_pocket)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> ChatSession:
    """Get a specific chat session with full history."""
    session = chat_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 100,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> list[dict[str, Any]]:
    """Get messages for a specific session."""
    session = chat_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return chat_repo.get_session_messages(session_id, limit=limit)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    title: str | None = None,
    is_archived: bool | None = None,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> dict[str, str]:
    """Update a chat session's title or archive status."""
    if not chat_repo.update_session(session_id, title=title, is_archived=is_archived):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "updated", "session_id": session_id}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> dict[str, str]:
    """Delete a chat session."""
    if not chat_repo.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.delete("/sessions")
async def clear_sessions(
    rag_pocket: str | None = None,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> dict[str, str]:
    """Clear all chat sessions (optionally filtered by pocket)."""
    count = chat_repo.clear_sessions(rag_pocket=rag_pocket)
    return {"status": "cleared", "count": str(count)}


@router.get("/search")
async def search_messages(
    query: str,
    rag_pocket: str | None = None,
    limit: int = 50,
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> list[dict[str, Any]]:
    """Search messages across all sessions."""
    return chat_repo.search_messages(query=query, rag_pocket=rag_pocket, limit=limit)
