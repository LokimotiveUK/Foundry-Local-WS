"""Command-line interface for Mac Assistant."""

from __future__ import annotations

import argparse
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mac Desktop AI Assistant",
        prog="mac-assistant",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("serve", help="Start the API server")
    server_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    server_parser.add_argument(
        "--model",
        help="Model to load on startup",
    )
    server_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    # Chat command (simple CLI chat)
    chat_parser = subparsers.add_parser("chat", help="Start interactive chat")
    chat_parser.add_argument(
        "--model",
        help="Model to use for chat",
    )
    chat_parser.add_argument(
        "--pocket",
        help="RAG pocket to use",
    )

    # Models command
    models_parser = subparsers.add_parser("models", help="Manage models")
    models_parser.add_argument(
        "action",
        choices=["list", "download", "load", "unload"],
        help="Action to perform",
    )
    models_parser.add_argument(
        "model_name",
        nargs="?",
        help="Model name (for download/load/unload)",
    )

    args = parser.parse_args()

    if args.command == "serve":
        run_server(args)
    elif args.command == "chat":
        run_chat(args)
    elif args.command == "models":
        manage_models(args)
    else:
        parser.print_help()
        sys.exit(1)


def run_server(args):
    """Start the API server."""
    import uvicorn

    from src.core.config import get_settings

    settings = get_settings()

    # Override settings from args
    host = args.host or settings.api_host
    port = args.port or settings.api_port

    if args.model:
        settings.default_model = args.model

    print(f"Starting Mac Assistant API at http://{host}:{port}")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level="info",
    )


def run_chat(args):
    """Start interactive CLI chat."""
    from src.core.config import get_settings
    from src.foundry.manager import FoundryManager
    from src.foundry.metrics import format_metrics
    from src.foundry.streaming import StreamingHandler

    settings = get_settings()
    model = args.model or settings.default_model

    print(f"Initializing Mac Assistant with model: {model}")
    print("Type 'quit' or 'exit' to stop, 'clear' to reset conversation")
    print("-" * 50)

    try:
        manager = FoundryManager()
        manager.initialize(model)
    except Exception as e:
        print(f"Error: Failed to initialize Foundry: {e}")
        sys.exit(1)

    messages = []

    # Add system prompt if pocket specified
    if args.pocket:
        from src.core.config import DEFAULT_POCKETS
        if args.pocket in DEFAULT_POCKETS:
            pocket = DEFAULT_POCKETS[args.pocket]
            messages.append({
                "role": "system",
                "content": pocket["system_prompt"],
            })
            print(f"Using RAG pocket: {args.pocket}")
            print("-" * 50)

    handler = StreamingHandler(
        client=manager.client,
        model_id=manager.current_model_id,
        verbose=settings.verbose_mode,
    )

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if user_input.lower() == "clear":
            messages = messages[:1] if args.pocket else []
            print("Conversation cleared.")
            continue

        messages.append({"role": "user", "content": user_input})

        print("\nAssistant: ", end="", flush=True)

        full_response = ""
        for chunk in handler.stream_chat(
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_response_tokens,
        ):
            print(chunk.content, end="", flush=True)
            full_response += chunk.content

            if chunk.done and settings.verbose_mode and chunk.metrics:
                print(f"\n[{format_metrics(chunk.metrics)}]")

        messages.append({"role": "assistant", "content": full_response})


def manage_models(args):
    """Manage AI models."""
    from src.foundry.manager import FoundryManager

    manager = FoundryManager()

    try:
        manager.initialize()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.action == "list":
        print("\nAvailable Models:")
        print("-" * 60)

        cached = {m.id for m in manager.list_cached_models()}
        loaded = {m.id for m in manager.list_loaded_models()}

        for model in manager.list_catalog_models():
            status = []
            if model.id in cached:
                status.append("downloaded")
            if model.id in loaded:
                status.append("loaded")

            status_str = f" [{', '.join(status)}]" if status else ""
            print(f"  {model.alias:<30} {model.device_type:<6}{status_str}")

    elif args.action == "download":
        if not args.model_name:
            print("Error: Model name required for download")
            sys.exit(1)

        print(f"Downloading {args.model_name}...")
        try:
            info = manager.download_model(args.model_name)
            print(f"Downloaded: {info.id}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.action == "load":
        if not args.model_name:
            print("Error: Model name required for load")
            sys.exit(1)

        print(f"Loading {args.model_name}...")
        try:
            info = manager.load_model(args.model_name)
            print(f"Loaded: {info.id}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.action == "unload":
        if not args.model_name:
            print("Error: Model name required for unload")
            sys.exit(1)

        print(f"Unloading {args.model_name}...")
        try:
            manager.unload_model(args.model_name)
            print("Unloaded successfully")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
