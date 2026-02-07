#!/usr/bin/env python3
"""
Voice Chess CLI - Entry point for the chess application.
Usage: chess [options]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_frontend():
    """Build the Svelte frontend if needed."""
    project_root = Path(__file__).parent.parent
    frontend_dir = project_root / "frontend"
    dist_dir = project_root / "static" / "dist"

    # Check if frontend exists
    if not frontend_dir.exists():
        return True  # No frontend to build, use legacy

    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("    Installing frontend dependencies...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=frontend_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"    Warning: npm install failed: {result.stderr}")
            return False

    # Check if build is needed (dist doesn't exist or is older than src)
    needs_build = not dist_dir.exists()

    if not needs_build:
        # Check if any source file is newer than dist
        src_dir = frontend_dir / "src"
        if src_dir.exists():
            dist_mtime = dist_dir.stat().st_mtime
            for src_file in src_dir.rglob("*"):
                if src_file.is_file() and src_file.stat().st_mtime > dist_mtime:
                    needs_build = True
                    break

    if needs_build:
        print("    Building frontend...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"    Warning: Build failed: {result.stderr}")
            return False
        print("    Frontend built successfully")

    return True


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
  chess --text              Run in text-only mode (for debugging)

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
        default=8766,
        help="Port to run server on (default: 8766)"
    )

    parser.add_argument(
        "--model", "-m",
        default="qwen2.5:14b",
        help="Ollama model to use (default: qwen2.5:14b)"
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

    parser.add_argument(
        "--text", "-t",
        action="store_true",
        help="Run in text-only mode (no browser, terminal interface)"
    )

    args = parser.parse_args()

    # Text mode - run the debug CLI instead
    if args.text:
        import asyncio
        from .debug_cli import DebugCLI
        cli = DebugCLI(model=args.model)
        asyncio.run(cli.run())
        return

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

            # Check if requested model is available
            model_available = args.model in models or any(args.model in m for m in models)
            if not model_available:
                print(f"    Warning: Model '{args.model}' not found")
                print(f"    Available: {', '.join(models[:5])}")
                # Try to find a suitable fallback
                preferred = ['qwen2.5:14b', 'qwen2.5:7b', 'llama3.1', 'llama3.2', 'llama3', 'mistral']
                for pref in preferred:
                    if any(pref in m for m in models):
                        fallback = next(m for m in models if pref in m)
                        args.model = fallback
                        os.environ["CHESS_MODEL"] = fallback
                        print(f"    Using fallback: {fallback}")
                        break
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

    # Build frontend if needed
    build_frontend()

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
