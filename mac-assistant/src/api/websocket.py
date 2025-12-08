"""WebSocket endpoint for real-time chat streaming."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.config import DEFAULT_POCKETS, get_settings
from src.core.models import ChatSession, MessageRole, StreamChunk
from src.foundry.manager import get_foundry_manager
from src.foundry.metrics import format_metrics
from src.foundry.streaming import StreamingHandler
from src.storage.chats import get_chat_repository

logger = logging.getLogger(__name__)

websocket_router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and register a new connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")

    def disconnect(self, client_id: str) -> None:
        """Remove a connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")

    async def send_json(self, client_id: str, data: dict[str, Any]) -> None:
        """Send JSON data to a specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast to all connections."""
        for connection in self.active_connections.values():
            await connection.send_json(data)


manager = ConnectionManager()


@websocket_router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat.

    Message format (client -> server):
    {
        "type": "message",
        "content": "User message here",
        "session_id": "optional-session-id",
        "rag_pocket": "optional-pocket-name",
        "temperature": 0.7,  // optional
        "max_tokens": 2048   // optional
    }

    Response format (server -> client):
    {
        "type": "chunk",
        "content": "Token content",
        "done": false,
        "metrics": {...}
    }

    Final response:
    {
        "type": "complete",
        "session_id": "session-id",
        "model": "model-name",
        "metrics": {...}
    }

    Error response:
    {
        "type": "error",
        "message": "Error description"
    }
    """
    client_id = str(uuid4())
    await manager.connect(websocket, client_id)

    foundry = get_foundry_manager()
    settings = get_settings()
    chat_repo = get_chat_repository()

    try:
        # Send connection acknowledgment
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "foundry_ready": foundry.is_initialized,
            "current_model": foundry.current_model if foundry.is_initialized else None,
        })

        while True:
            # Receive message
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if data.get("type") != "message":
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {data.get('type')}",
                })
                continue

            # Check Foundry status
            if not foundry.is_initialized:
                await websocket.send_json({
                    "type": "error",
                    "message": "Foundry not initialized. Please wait or restart the server.",
                })
                continue

            # Extract message parameters
            content = data.get("content", "").strip()
            if not content:
                await websocket.send_json({
                    "type": "error",
                    "message": "Empty message content",
                })
                continue

            session_id = data.get("session_id")
            rag_pocket = data.get("rag_pocket")
            temperature = data.get("temperature", settings.temperature)
            max_tokens = data.get("max_tokens", settings.max_response_tokens)

            # Get or create session from database
            session = chat_repo.get_or_create_session(
                session_id,
                foundry.current_model or settings.default_model,
                rag_pocket,
            )

            # Add user message to database
            chat_repo.add_message(session.id, MessageRole.USER, content)

            # Build messages for API
            messages = []

            # Add system prompt if RAG pocket specified
            if rag_pocket and rag_pocket in DEFAULT_POCKETS:
                pocket_config = DEFAULT_POCKETS[rag_pocket]
                messages.append({
                    "role": "system",
                    "content": pocket_config.get("system_prompt", "You are a helpful assistant."),
                })

            # Add conversation history from database
            db_messages = chat_repo.get_session_messages(session.id, limit=settings.context_window)
            messages.extend([{"role": m["role"], "content": m["content"]} for m in db_messages])

            # Create streaming handler
            model_id = foundry.current_model_id
            if not model_id:
                await websocket.send_json({
                    "type": "error",
                    "message": "No model loaded",
                })
                continue

            handler = StreamingHandler(
                client=foundry.client,
                model_id=model_id,
                verbose=settings.verbose_mode,
            )

            # Send acknowledgment
            await websocket.send_json({
                "type": "start",
                "session_id": session.id,
                "model": foundry.current_model,
            })

            # Stream response
            full_response = ""
            final_metrics = None

            try:
                async for chunk in handler.stream_chat_async(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    full_response += chunk.content

                    if chunk.done:
                        final_metrics = chunk.metrics
                    else:
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk.content,
                            "done": False,
                            "metrics": chunk.metrics.model_dump() if chunk.metrics else None,
                        })

                # Add assistant message to database with metrics
                chat_repo.add_message(
                    session.id,
                    MessageRole.ASSISTANT,
                    full_response,
                    metrics=final_metrics,
                )

                # Send completion
                await websocket.send_json({
                    "type": "complete",
                    "session_id": session.id,
                    "model": foundry.current_model,
                    "rag_pocket": rag_pocket,
                    "metrics": final_metrics.model_dump() if final_metrics else None,
                })

                if settings.verbose_mode and final_metrics:
                    logger.info(f"WebSocket response: {format_metrics(final_metrics)}")

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Streaming error: {str(e)}",
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)


@websocket_router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """WebSocket endpoint for real-time metrics updates.

    Sends periodic updates about system state.
    Useful for displaying live tokens/second during generation.
    """
    client_id = f"metrics-{uuid4()}"
    await manager.connect(websocket, client_id)

    foundry = get_foundry_manager()

    try:
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
        })

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                # Send current system state
                metrics = {
                    "type": "metrics",
                    "foundry_ready": foundry.is_initialized,
                    "current_model": foundry.current_model if foundry.is_initialized else None,
                }

                if foundry.is_initialized:
                    try:
                        loaded = foundry.list_loaded_models()
                        metrics["loaded_models"] = len(loaded)
                    except Exception:
                        pass

                await websocket.send_json(metrics)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Metrics WebSocket error: {e}")
        manager.disconnect(client_id)
