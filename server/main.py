"""
FastAPI server for Voice Chess with Ollama.
Provides REST API and WebSocket for real-time game communication.
"""

import asyncio
import json
import logging
import os
import webbrowser
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .game import ChessGame
from .ollama_client import OllamaClient
from .engine import ChessEngine, get_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Global state
games: dict[str, ChessGame] = {}
ollama_client: Optional[OllamaClient] = None

# Games directory for PGN files
GAMES_DIR = Path(__file__).parent.parent / "games"
GAMES_DIR.mkdir(exist_ok=True)


def save_game_pgn(game: ChessGame, filename: str = None) -> Path:
    """Save game to PGN file."""
    from datetime import datetime
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"game_{timestamp}.pgn"
    filepath = GAMES_DIR / filename
    pgn_content = game.get_pgn()
    filepath.write_text(pgn_content)
    logger.info(f"Game saved: {filepath}")
    return filepath


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global ollama_client

    # Startup - Initialize Stockfish engine
    engine = get_engine()
    if engine.is_running():
        logger.info(f"Stockfish engine ready (skill level: {engine.skill_level})")
    else:
        logger.warning("Stockfish not available - install with: brew install stockfish")

    # Initialize Ollama for commentary
    model = os.environ.get("CHESS_MODEL", "qwen2.5:14b")
    ollama_client = OllamaClient(model=model)

    if await ollama_client.check_connection():
        logger.info(f"Ollama connected (model: {model}) - for move explanations")
    else:
        logger.warning("Ollama not running - AI commentary disabled")

    yield

    # Shutdown
    if ollama_client:
        await ollama_client.close()
    engine.stop()


app = FastAPI(
    title="Voice Chess",
    description="Play chess against Ollama using your voice",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Pydantic models
class NewGameRequest(BaseModel):
    player_color: str = "white"
    model: Optional[str] = None


class MoveRequest(BaseModel):
    move: str


class ChatRequest(BaseModel):
    message: str


# REST endpoints
@app.get("/")
async def root():
    """Serve the main HTML page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Voice Chess API", "docs": "/docs"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    ollama_ok = await ollama_client.check_connection() if ollama_client else False
    return {
        "status": "ok",
        "ollama_connected": ollama_ok,
        "model": ollama_client.model if ollama_client else None
    }


@app.get("/api/models")
async def list_models():
    """List available Ollama models."""
    if not ollama_client:
        return {"models": []}
    models = await ollama_client.list_models()
    return {"models": models}


@app.post("/api/game/new")
async def new_game(request: NewGameRequest):
    """Start a new chess game."""
    global ollama_client

    game_id = "default"
    game = ChessGame()
    state = game.new_game(request.player_color)
    games[game_id] = game

    if request.model and ollama_client:
        ollama_client.model = request.model

    logger.info(f"New game started: {game_id}, player is {request.player_color}")
    return {"game_id": game_id, "state": state}


@app.get("/api/game/{game_id}")
async def get_game(game_id: str):
    """Get current game state."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.state.to_dict()


@app.post("/api/game/{game_id}/move")
async def make_move(game_id: str, request: MoveRequest):
    """Make a move in the game."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    result = game.make_move(request.move)
    return result


@app.post("/api/game/{game_id}/undo")
async def undo_move(game_id: str):
    """Undo the last move pair."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    result = game.undo_last_pair()
    return result


@app.get("/api/game/{game_id}/pgn")
async def get_pgn(game_id: str):
    """Get PGN of the game."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return {"pgn": game.get_pgn()}


# WebSocket for real-time communication
@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """
    WebSocket endpoint for real-time game communication.

    Message types:
    - new_game: Start a new game
    - move: Make a player move
    - chat: Send a chat message (may include a move or question)
    - undo: Undo last move pair
    - get_state: Request current game state
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: {game_id}")

    # Ensure game exists
    if game_id not in games:
        games[game_id] = ChessGame()

    game = games[game_id]

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            logger.info(f"Received message: {msg_type}")

            if msg_type == "new_game":
                player_color = data.get("player_color", "white")
                model = data.get("model")

                if model and ollama_client:
                    ollama_client.model = model

                state = game.new_game(player_color)
                await websocket.send_json({
                    "type": "game_state",
                    "state": state
                })

                # If player is black, AI moves first
                if player_color == "black":
                    await handle_ai_turn(websocket, game, "Let's begin. You're White, make your opening move.")

            elif msg_type == "move":
                # Player makes a move
                move_str = data.get("move", "")
                result = game.make_move(move_str)

                await websocket.send_json({
                    "type": "move_result",
                    "result": result
                })

                # If move was successful and it's now AI's turn
                if result["success"] and game.is_ai_turn() and not game.state.board.is_game_over():
                    await handle_ai_turn(websocket, game, f"I played {result['move']}.")

            elif msg_type == "chat":
                # Handle chat message - could be a move, question, or command
                message = data.get("message", "")
                await handle_chat(websocket, game, message)

            elif msg_type == "undo":
                result = game.undo_last_pair()
                await websocket.send_json({
                    "type": "undo_result",
                    "result": result
                })

            elif msg_type == "get_state":
                await websocket.send_json({
                    "type": "game_state",
                    "state": game.state.to_dict()
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {game_id}")
        # Save game on disconnect if there are moves
        if game and game.state.board.move_stack:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_game_pgn(game, f"game_{timestamp}_session.pgn")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass


async def handle_chat(websocket: WebSocket, game: ChessGame, message: str):
    """Handle a chat message from the player."""
    message_lower = message.lower().strip()

    # Check for commands
    if any(word in message_lower for word in ["undo", "take back", "takeback"]):
        result = game.undo_last_pair()
        await websocket.send_json({
            "type": "undo_result",
            "result": result
        })
        await websocket.send_json({
            "type": "ai_response",
            "message": "No problem, I've taken back the last moves. Your turn again!",
            "move": None
        })
        return

    # Check for move count question
    if any(phrase in message_lower for phrase in ["how many moves", "move count", "how many turns"]):
        state = game.state.to_dict()
        count = state["half_moves"]
        full = state["full_moves"]
        response = f"We've played {count} half-moves, which is {full} full moves. "
        if game.is_ai_turn():
            response += "It's my turn."
        else:
            response += "It's your turn."

        await websocket.send_json({
            "type": "ai_response",
            "message": response,
            "move": None
        })
        return

    # Try to parse as a move first
    move_result = try_parse_player_move(message, game)
    if move_result:
        result = game.make_move(move_result)
        if result["success"]:
            logger.info(f"[PLAYER MOVE] {result['move']}")
            save_game_pgn(game, "current_game.pgn")

            await websocket.send_json({
                "type": "move_result",
                "result": result
            })

            # AI responds and moves
            if game.is_ai_turn() and not game.state.board.is_game_over():
                await handle_ai_turn(websocket, game, f"I played {result['move']}.")
            return

    # Check for ambiguous move requests and help the player
    ambiguous_patterns = [
        "move the", "move a", "push the", "push a", "advance",
        "forward", "go forward", "move forward"
    ]
    if any(p in message_lower for p in ambiguous_patterns):
        legal = game.get_legal_moves()
        # Try to identify what they meant
        pawn_moves = [m for m in legal if len(m) == 2 and m[0] in 'abcdefgh']

        response = "I'm not sure which piece you want to move. "
        if pawn_moves:
            response += f"Your pawn moves are: {', '.join(pawn_moves[:8])}. "
        response += "Try saying something like 'e4' or 'knight to f3'."

        await websocket.send_json({
            "type": "ai_response",
            "message": response,
            "move": None
        })
        return

    # Not a move - send to AI for conversation
    await handle_ai_turn(websocket, game, message)


def try_parse_player_move(text: str, game: ChessGame) -> Optional[str]:
    """
    Try to extract a chess move from player's spoken/typed text.
    Returns the move string if found, None otherwise.
    """
    import re
    text_lower = text.lower().strip()

    # Normalize: remove extra spaces, handle "e 4" -> "e4"
    normalized = re.sub(r'([a-h])\s+([1-8])', r'\1\2', text_lower)
    # Handle "knight f 3" -> "knight f3"
    normalized = re.sub(r'([a-h])\s+([1-8])', r'\1\2', normalized)

    # Handle castling - various spoken forms
    castling_kingside = ["castle kingside", "castle king side", "short castle",
                         "castles kingside", "castle short", "kingside castle",
                         "castle king", "oh oh", "o-o"]
    castling_queenside = ["castle queenside", "castle queen side", "long castle",
                          "castles queenside", "castle long", "queenside castle",
                          "castle queen", "oh oh oh", "o-o-o"]

    if any(phrase in text_lower for phrase in castling_kingside):
        return "O-O"
    if any(phrase in text_lower for phrase in castling_queenside):
        return "O-O-O"

    # Standard algebraic notation (with normalized text)
    san_pattern = r'\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b'
    match = re.search(san_pattern, normalized, re.IGNORECASE)
    if match:
        return match.group(1)

    # Spoken format: "knight to f3", "bishop takes c6", "pawn e4"
    piece_map = {
        "knight": "N", "bishop": "B", "rook": "R",
        "queen": "Q", "king": "K", "pawn": ""
    }

    # Pattern handles: "knight to f3", "knight f3", "bishop takes c6", etc.
    spoken_pattern = r'\b(knight|bishop|rook|queen|king|pawn)?\s*(?:to|takes?|captures?|on)?\s*([a-h])\s*([1-8])\b'
    match = re.search(spoken_pattern, normalized)
    if match:
        piece = piece_map.get(match.group(1), "") if match.group(1) else ""
        file = match.group(2)
        rank = match.group(3)
        return f"{piece}{file}{rank}"

    # Handle spoken numbers: "e four", "knight f three"
    number_words = {"one": "1", "two": "2", "three": "3", "four": "4",
                    "five": "5", "six": "6", "seven": "7", "eight": "8"}
    for word, digit in number_words.items():
        normalized = normalized.replace(word, digit)

    # Try pattern again with number words replaced
    match = re.search(san_pattern, normalized, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(spoken_pattern, normalized)
    if match:
        piece = piece_map.get(match.group(1), "") if match.group(1) else ""
        file = match.group(2)
        rank = match.group(3)
        return f"{piece}{file}{rank}"

    return None


async def handle_ai_turn(websocket: WebSocket, game: ChessGame, player_message: str):
    """
    Handle AI's turn using Stockfish for moves, Ollama for commentary.

    Architecture:
    - Stockfish: Generates strong, tactically sound moves
    - Ollama: Explains the move and handles conversation
    """
    # Send thinking indicator
    await websocket.send_json({
        "type": "ai_thinking",
        "thinking": True
    })

    is_ai_turn = game.is_ai_turn()
    logger.info(f"[PLAYER] {player_message}")

    try:
        ai_move = None
        engine_analysis = None

        # If it's AI's turn, use Stockfish for the move
        if is_ai_turn:
            engine = get_engine()

            if engine.is_running():
                # Get Stockfish's best move
                result = engine.get_best_move(game.state.board)

                if result:
                    move, analysis = result
                    engine_analysis = analysis

                    # Log engine thinking
                    logger.info(f"[STOCKFISH] Best: {analysis['move']}, Eval: {analysis['score']}, "
                               f"Depth: {analysis['depth']}, Line: {' '.join(analysis['pv'])}")

                    # Make the move
                    move_result = game.make_move(analysis['move'])
                    if move_result["success"]:
                        ai_move = move_result["move"]
                        logger.info(f"[ENGINE MOVE] {ai_move}")
                        save_game_pgn(game, "current_game.pgn")
            else:
                # Fallback: pick a reasonable move without engine
                legal_moves = game.get_legal_moves()
                if legal_moves:
                    priority = ['e5', 'd5', 'Nf6', 'Nc6', 'e6', 'd6', 'Bc5', 'Be7', 'O-O', 'c5']
                    fallback = next((m for m in priority if m in legal_moves), legal_moves[0])
                    move_result = game.make_move(fallback)
                    if move_result["success"]:
                        ai_move = move_result["move"]
                        logger.info(f"[FALLBACK MOVE] {ai_move}")
                        save_game_pgn(game, "current_game.pgn")

        # Generate natural language response using Ollama
        response = await generate_move_commentary(
            game, player_message, ai_move, engine_analysis, is_ai_turn
        )

        # Store in conversation history
        game.add_conversation("user", player_message)
        game.add_conversation("assistant", response)

        await websocket.send_json({
            "type": "ai_response",
            "message": response,
            "move": ai_move,
            "state": game.state.to_dict()
        })

        # Check for game over
        if game.state.board.is_game_over():
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_game_pgn(game, f"game_{timestamp}_final.pgn")
            result = game.state.get_result()
            logger.info(f"[GAME OVER] {result}")

    except Exception as e:
        logger.error(f"AI turn error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": f"AI error: {str(e)}"
        })

    finally:
        await websocket.send_json({
            "type": "ai_thinking",
            "thinking": False
        })


async def generate_move_commentary(
    game: ChessGame,
    player_message: str,
    ai_move: Optional[str],
    engine_analysis: Optional[dict],
    is_ai_turn: bool
) -> str:
    """
    Generate natural language commentary for a move or respond to questions.

    Uses Ollama for conversational responses, but keeps them SHORT for speech.
    """
    # If no Ollama, just return the move
    if not ollama_client:
        if ai_move:
            return f"{ai_move}."
        return "Your turn."

    # Check if this is a question (tutor mode) or just a move notification
    is_question = any(word in player_message.lower() for word in
                      ['why', 'what', 'how', 'explain', 'help', 'hint', '?'])

    if is_question and not is_ai_turn:
        # Tutor mode - give a detailed explanation
        game_context = f"""Position: {game.get_formatted_history()}
{game.get_position_description()}

The player asked: "{player_message}"

Give a helpful, educational response about chess strategy or the position."""

        response = await ollama_client.chat(
            user_message=player_message,
            game_context=game_context,
            conversation_history=game.get_conversation_history()[-4:],
            is_ai_turn=False,
            legal_moves=[]
        )
        logger.info(f"[TUTOR] {response}")
        return response

    elif ai_move:
        # Just made a move - give a VERY brief comment
        # Build context about what the move does
        eval_info = ""
        if engine_analysis:
            score = engine_analysis.get('score', '0.0')
            eval_info = f"Position evaluation: {score}"

        context = f"""You just played {ai_move}.
{eval_info}
Say your move and add ONE short comment (max 8 words). Be natural, like talking to a friend.
Examples: "{ai_move}." or "{ai_move}, developing my knight." or "I'll take that pawn."""

        try:
            response = await ollama_client.chat(
                user_message=f"I played, now it's your turn. You play {ai_move}.",
                game_context=context,
                conversation_history=[],
                is_ai_turn=False,  # We already made the move
                legal_moves=[]
            )

            # Clean and shorten the response
            import re
            response = re.sub(r'\*\*[^*]+\*\*', '', response)
            response = response.strip()

            # If response is too long, just use the move
            if len(response) > 80:
                response = f"{ai_move}."

            logger.info(f"[COMMENT] {response}")
            return response

        except Exception as e:
            logger.error(f"Commentary error: {e}")
            return f"{ai_move}."

    else:
        # No move, just conversation
        return "Your turn."


def run_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """Run the FastAPI server."""
    import uvicorn

    if open_browser:
        # Open browser after a short delay
        def open_browser_delayed():
            import time
            time.sleep(1.5)
            url = f"http://{host}:{port}"
            webbrowser.open(url)
            print(f"\n  Browser opened to {url}")

        import threading
        threading.Thread(target=open_browser_delayed, daemon=True).start()

    print(f"""
    +-----------------------------------------+
    |         VOICE CHESS with OLLAMA         |
    +-----------------------------------------+
    |  Server running at http://{host}:{port}  |
    |  Press Ctrl+C to stop                   |
    +-----------------------------------------+
    """)

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
