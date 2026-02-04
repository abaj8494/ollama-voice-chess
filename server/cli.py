#!/usr/bin/env python3
"""
Voice Chess CLI - Entry point for the chess application.
Usage: chess [options]
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Voice Chess - Play chess against Ollama using your voice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chess                     Start with default settings
  chess --model llama3.1    Use a specific Ollama model
  chess --port 9000         Use a different port
  chess --no-browser        Don't open browser automatically

Requirements:
  - Ollama running locally (ollama serve)
  - A model pulled (e.g., ollama pull llama3.2)
"""
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind server to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="Port to run server on (default: 8765)"
    )

    parser.add_argument(
        "--model", "-m",
        default="llama3.2",
        help="Ollama model to use (default: llama3.2)"
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Set environment variables for the server
    os.environ["CHESS_MODEL"] = args.model

    if args.debug:
        os.environ["CHESS_DEBUG"] = "1"

    # Print banner
    print("""
    ╔══════════════════════════════════════════╗
    ║                                          ║
    ║      ♔  VOICE CHESS with OLLAMA  ♚      ║
    ║                                          ║
    ║   Play chess using your voice against    ║
    ║   a locally-hosted AI opponent           ║
    ║                                          ║
    ╚══════════════════════════════════════════╝
    """)

    print(f"    Model: {args.model}")
    print(f"    Server: http://{args.host}:{args.port}")
    print()

    # Check if Ollama is running
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            print(f"    Ollama: Connected ({len(models)} models available)")
            if args.model not in models and not any(args.model in m for m in models):
                print(f"    Warning: Model '{args.model}' may not be available")
                print(f"    Available: {', '.join(models[:5])}")
        else:
            print("    Ollama: Connection issues")
    except Exception:
        print("    Ollama: Not running!")
        print()
        print("    Please start Ollama first:")
        print("      $ ollama serve")
        print()
        print("    And make sure you have a model:")
        print("      $ ollama pull llama3.2")
        print()
        sys.exit(1)

    print()
    print("    Press Ctrl+C to stop")
    print()

    # Import and run server
    from .main import run_server
    run_server(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser
    )


if __name__ == "__main__":
    main()
