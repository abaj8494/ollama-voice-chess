"""
FastAPI server for Voice Chess with Ollama.
Provides REST API and WebSocket for real-time game communication.
"""

import asyncio
import chess
import chess.pgn
import io
import json
import logging
import os
import webbrowser
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .game import ChessGame
from .ollama_client import OllamaClient
from .engine import ChessEngine, get_engine, set_engine_skill
from .tts import text_to_speech, get_voice_options, VOICES
from .stats import (
    load_stats, get_current_difficulty, set_difficulty,
    get_stats_summary, record_game, get_difficulty_name
)
from .analysis import check_blunder, analyze_game, get_position_assessment
from .tactics import analyze_tactics, get_tactical_summary
from .openings import OPENINGS, get_opening_by_id, get_all_openings
from .training import (
    TrainingSession, TrainingStats, TrainingProgress,
    load_training_stats, save_training_stats, calculate_hint_level,
    get_piece_hint, record_training_session, ensure_training_games_dir,
    TRAINING_GAMES_DIR
)
from .spaced_repetition import (
    ReviewCard, ReviewSession, CardType,
    get_review_manager, generate_opening_review_cards
)

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
training_sessions: dict[str, TrainingSession] = {}
review_sessions: dict[str, ReviewSession] = {}

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

    # Startup - Initialize Stockfish engine with saved difficulty
    saved_difficulty = get_current_difficulty()
    engine = get_engine()
    if engine.is_running():
        engine.set_skill_level(saved_difficulty)
        logger.info(f"Stockfish engine ready (skill level: {saved_difficulty} - {get_difficulty_name(saved_difficulty)})")
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

# Static files - serve Svelte build from static/dist
static_dir = Path(__file__).parent.parent / "static"
dist_dir = static_dir / "dist"

# Serve assets (JS, CSS) from dist/assets
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")
    app.mount("/pieces", StaticFiles(directory=str(dist_dir / "pieces")), name="pieces")


# Pydantic models
class NewGameRequest(BaseModel):
    player_color: str = "white"
    model: Optional[str] = None


class MoveRequest(BaseModel):
    move: str


class ChatRequest(BaseModel):
    message: str


class DifficultyRequest(BaseModel):
    level: int


class SaveGameRequest(BaseModel):
    name: Optional[str] = None


class GameResultRequest(BaseModel):
    result: str  # "win", "loss", "draw"
    name: Optional[str] = None


class StartTrainingRequest(BaseModel):
    opening_id: str


class TrainingMoveRequest(BaseModel):
    move: str


class StartReviewRequest(BaseModel):
    card_limit: int = 20
    card_type: Optional[str] = None


class ReviewAnswerRequest(BaseModel):
    move: str


# REST endpoints
@app.get("/")
async def root():
    """Serve the Svelte SPA."""
    # Try dist first (Svelte build), fall back to legacy index.html
    dist_index = dist_dir / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)
    legacy_index = static_dir / "index.html"
    if legacy_index.exists():
        return FileResponse(legacy_index)
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


@app.get("/api/voices")
async def list_voices():
    """List available TTS voices."""
    return {"voices": get_voice_options()}


class TTSRequest(BaseModel):
    text: str
    voice: str = "ryan"
    rate: str = "+0%"


@app.post("/api/tts")
async def synthesize_speech(request: TTSRequest):
    """
    Convert text to speech using neural TTS.

    Returns MP3 audio data.
    """
    logger.info(f"[TTS] Request: voice={request.voice}, text={request.text[:50]}...")
    try:
        audio_data = await text_to_speech(
            text=request.text,
            voice=request.voice,
            rate=request.rate
        )
        logger.info(f"[TTS] Generated {len(audio_data)} bytes")
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"}
        )
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Stats and difficulty endpoints
@app.get("/api/stats")
async def get_player_stats():
    """Get player statistics summary."""
    return get_stats_summary()


@app.get("/api/difficulty")
async def get_difficulty():
    """Get current difficulty level."""
    level = get_current_difficulty()
    return {
        "level": level,
        "name": get_difficulty_name(level),
        "min": 1,
        "max": 20
    }


@app.post("/api/difficulty")
async def update_difficulty(request: DifficultyRequest):
    """Set difficulty level manually."""
    new_level = set_difficulty(request.level)
    # Also update engine skill
    set_engine_skill(new_level)
    return {
        "level": new_level,
        "name": get_difficulty_name(new_level)
    }


@app.post("/api/game/{game_id}/save")
async def save_game(game_id: str, request: SaveGameRequest):
    """Save current game with optional name."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_slug = request.name.replace(" ", "_")[:30] if request.name else "game"
    filename = f"{name_slug}_{timestamp}.pgn"

    filepath = save_game_pgn(game, filename)
    return {"filename": str(filepath), "name": request.name or "Unnamed Game"}


@app.get("/api/games/saved")
async def list_saved_games():
    """List all saved games in reverse chronological order."""
    import os
    from datetime import datetime

    saved_games = []
    if GAMES_DIR.exists():
        for filepath in sorted(GAMES_DIR.glob("*.pgn"), key=os.path.getmtime, reverse=True):
            try:
                content = filepath.read_text()
                # Parse PGN to get game info
                pgn_io = io.StringIO(content)
                pgn_game = chess.pgn.read_game(pgn_io)

                if pgn_game:
                    headers = dict(pgn_game.headers)
                    # Count moves
                    move_count = len(list(pgn_game.mainline_moves()))

                    # Get file modification time
                    mtime = os.path.getmtime(filepath)
                    date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

                    # Extract name from filename
                    name = filepath.stem.replace("_", " ")
                    # Remove timestamp suffix if present
                    if len(name) > 15 and name[-15:-7].isdigit():
                        name = name[:-16]

                    # Determine player color from headers
                    white_player = headers.get("White", "?")
                    black_player = headers.get("Black", "?")
                    if "Human" in white_player or "Player" in white_player:
                        player_color = "white"
                    elif "Human" in black_player or "Player" in black_player:
                        player_color = "black"
                    else:
                        player_color = "white"  # Default

                    saved_games.append({
                        "filename": filepath.name,
                        "name": name or "Unnamed Game",
                        "date": date_str,
                        "white": white_player,
                        "black": black_player,
                        "player_color": player_color,
                        "result": headers.get("Result", "*"),
                        "moves": move_count // 2,  # Full moves
                        "is_complete": headers.get("Result", "*") != "*",
                    })
            except Exception as e:
                logger.error(f"Error reading {filepath}: {e}")
                continue

    return {"games": saved_games[:50]}  # Limit to 50 most recent


class LoadGameRequest(BaseModel):
    filename: str
    player_color: Optional[str] = None  # If None, determine from PGN


@app.post("/api/games/load")
async def load_saved_game(request: LoadGameRequest):
    """Load a saved game from PGN file."""
    filepath = GAMES_DIR / request.filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Game file not found")

    try:
        content = filepath.read_text()
        pgn_io = io.StringIO(content)
        pgn_game = chess.pgn.read_game(pgn_io)

        if not pgn_game:
            raise HTTPException(status_code=400, detail="Invalid PGN file")

        # Determine player color from headers or request
        white_player = pgn_game.headers.get("White", "Human")
        black_player = pgn_game.headers.get("Black", "Ollama")

        if request.player_color:
            player_color = request.player_color
        elif "Human" in white_player or "Player" in white_player:
            player_color = "white"
        elif "Human" in black_player or "Player" in black_player:
            player_color = "black"
        else:
            player_color = "white"  # Default

        # Create new game and replay moves
        game_id = "default"
        game = ChessGame()
        game.new_game(player_color)

        # Replay all moves
        for move in pgn_game.mainline_moves():
            san = game.state.board.san(move)
            game.state.board.push(move)

        games[game_id] = game

        # Extract game name from filename
        game_name = request.filename.replace(".pgn", "").replace("_", " ")
        # Remove timestamp suffix if present (format: name_YYYYMMDD_HHMMSS)
        if len(game_name) > 15 and game_name[-15:-7].replace(" ", "").isdigit():
            game_name = game_name[:-16]

        return {
            "success": True,
            "game_id": game_id,
            "state": game.state.to_dict(),
            "player_color": player_color,
            "filename": request.filename,
            "game_name": game_name.strip() or "Loaded Game",
        }

    except Exception as e:
        logger.error(f"Error loading game: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/{game_id}/record")
async def record_game_result(game_id: str, request: GameResultRequest):
    """Record a completed game result and update stats."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Save the game first
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_slug = request.name.replace(" ", "_")[:30] if request.name else "game"
    filename = f"{name_slug}_{timestamp}.pgn"
    filepath = save_game_pgn(game, filename)

    # Get game details
    player_color = game.state.player_color
    moves_count = len(game.state.board.move_stack)

    # Get final evaluation if engine available
    final_eval = None
    engine = get_engine()
    if engine.is_running():
        eval_result = engine.evaluate_position(game.state.board)
        try:
            final_eval = float(eval_result.get('score', 0))
        except (ValueError, TypeError):
            pass

    # Record the game
    stats = record_game(
        result=request.result,
        player_color=player_color,
        moves_count=moves_count,
        final_eval=final_eval,
        game_name=request.name,
        pgn_file=str(filepath)
    )

    return {
        "recorded": True,
        "new_difficulty": stats["current_difficulty"],
        "difficulty_name": get_difficulty_name(stats["current_difficulty"]),
        "stats": get_stats_summary()
    }


@app.get("/api/game/{game_id}/analysis")
async def analyze_current_game(game_id: str):
    """Analyze the current game for blunders and mistakes."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    pgn_text = game.get_pgn()
    analysis = analyze_game(pgn_text, depth=12)

    if not analysis:
        return {"error": "Analysis failed"}

    # Get starting position FEN
    starting_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    return {
        "summary": analysis.summary,
        "starting_fen": starting_fen,
        "white_blunders": analysis.white_blunders,
        "white_mistakes": analysis.white_mistakes,
        "white_inaccuracies": analysis.white_inaccuracies,
        "black_blunders": analysis.black_blunders,
        "black_mistakes": analysis.black_mistakes,
        "black_inaccuracies": analysis.black_inaccuracies,
        "critical_moments": analysis.critical_moments,
        "moves": [
            {
                "move_number": m.move_number,
                "color": m.color,
                "move": m.move_san,
                "classification": m.classification,
                "comment": m.comment,
                "eval_before": m.eval_before,
                "eval_after": m.eval_after,
                "eval_change": m.eval_change,
                "best_move": m.best_move,
                "is_capture": m.is_capture,
                "is_check": m.is_check,
                "is_sacrifice": m.is_sacrifice,
                "fen_after": m.fen_after,
            }
            for m in analysis.moves
        ]
    }


@app.get("/api/game/{game_id}/tactics")
async def get_tactics(game_id: str):
    """Get tactical analysis of the current position."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    motifs = analyze_tactics(game.state.board)
    return {
        "tactics": [
            {
                "type": m.type,
                "description": m.description,
                "severity": m.severity,
                "targets": [chess.square_name(sq) for sq in m.target_squares]
            }
            for m in motifs
        ],
        "summary": get_tactical_summary(game.state.board)
    }


@app.get("/api/game/{game_id}/position")
async def get_position_info(game_id: str):
    """Get detailed position assessment."""
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return get_position_assessment(game.state.board)


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


@app.delete("/api/game/{game_id}/delete")
async def delete_game(game_id: str):
    """Delete game and its backup PGN file."""
    # Remove from active games
    if game_id in games:
        del games[game_id]

    # Delete current_game.pgn backup
    backup_path = GAMES_DIR / "current_game.pgn"
    deleted = False
    if backup_path.exists():
        try:
            backup_path.unlink()
            deleted = True
            logger.info(f"Deleted game backup: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")

    return {"success": True, "deleted_backup": deleted}


# ==================== TRAINING MODE ENDPOINTS ====================

@app.get("/api/openings")
async def list_openings():
    """List all available openings with progress info."""
    stats = load_training_stats()
    result = []
    for opening in get_all_openings():
        progress = stats.get_opening_progress(opening.id)
        result.append({
            "id": opening.id,
            "name": opening.name,
            "color": opening.color.value,
            "response_to": opening.response_to,
            "description": opening.description,
            "move_count": len(opening.main_line),
            "mastery_level": progress.mastery_level,
            "sessions_completed": progress.sessions_completed,
            "average_accuracy": progress.average_accuracy,
        })
    return {"openings": result}


@app.get("/api/openings/{opening_id}")
async def get_opening_details(opening_id: str):
    """Get details for a specific opening."""
    opening = get_opening_by_id(opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Opening not found")

    stats = load_training_stats()
    progress = stats.get_opening_progress(opening_id)

    return {
        "opening": {
            "id": opening.id,
            "name": opening.name,
            "color": opening.color.value,
            "response_to": opening.response_to,
            "description": opening.description,
            "main_line": [
                {
                    "move": m.move_san,
                    "explanation": m.explanation,
                    "common_responses": m.common_responses,
                }
                for m in opening.main_line
            ],
            "typical_plans": opening.typical_plans,
            "key_squares": opening.key_squares,
        },
        "progress": {
            "sessions_completed": progress.sessions_completed,
            "moves_practiced": progress.moves_practiced,
            "average_accuracy": progress.average_accuracy,
            "mastery_level": progress.mastery_level,
            "current_hint_level": progress.current_hint_level,
        }
    }


@app.get("/api/training/stats")
async def get_training_stats():
    """Get overall training statistics."""
    stats = load_training_stats()
    return {
        "total_sessions": stats.total_sessions,
        "total_moves_practiced": stats.total_moves_practiced,
        "sessions_today": stats.sessions_today,
        "daily_goal": stats.daily_goal,
        "openings_progress": {
            op_id: {
                "mastery_level": p.mastery_level,
                "accuracy": p.average_accuracy,
                "sessions": p.sessions_completed,
            }
            for op_id, p in stats.opening_progress.items()
        }
    }


@app.post("/api/training/start")
async def start_training(request: StartTrainingRequest):
    """Start a new training session for an opening."""
    opening = get_opening_by_id(request.opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Opening not found")

    stats = load_training_stats()
    progress = stats.get_opening_progress(request.opening_id)
    hint_level = calculate_hint_level(progress)

    # Create session
    from datetime import datetime
    session_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session = TrainingSession(
        session_id=session_id,
        opening_id=request.opening_id,
        player_color=opening.color.value,
        hint_level=hint_level,
    )
    training_sessions[session_id] = session

    # Create a game for this training session
    game = ChessGame()
    game.new_game(opening.color.value)
    games[session_id] = game

    # If player is Black, AI needs to play White's first move
    opponent_first_move_from = None
    opponent_first_move_to = None
    if opening.color.value == "black" and opening.response_to:
        first_move = opening.response_to  # "e4" or "d4"
        move_result = game.make_move(first_move)
        session.opponent_first_move = first_move
        if move_result and move_result.get('success'):
            opponent_first_move_from = move_result.get('from')
            opponent_first_move_to = move_result.get('to')

    # Get first hint for player
    first_hint = None
    if session.current_move_index < len(opening.main_line):
        move_info = opening.main_line[session.current_move_index]
        first_hint = {
            "move": move_info.move_san if hint_level == "full" else None,
            "piece_hint": get_piece_hint(move_info.move_san) if hint_level == "partial" else None,
            "explanation": move_info.explanation,
            "level": hint_level,
        }

    # Generate review cards for this opening if they don't exist
    generate_opening_review_cards(request.opening_id)

    logger.info(f"Training session started: {session_id} for {opening.name}")
    return {
        "session_id": session_id,
        "opening": opening.name,
        "player_color": opening.color.value,
        "hint_level": hint_level,
        "state": game.state.to_dict(),
        "current_hint": first_hint,
        "total_moves": len(opening.main_line),
        "current_move_index": 0,
        "opponent_first_move": session.opponent_first_move,  # For defenses, shows White's first move
        "opponent_first_move_from": opponent_first_move_from,
        "opponent_first_move_to": opponent_first_move_to,
    }


@app.post("/api/training/{session_id}/move")
async def training_move(session_id: str, request: TrainingMoveRequest):
    """Make a move in a training session."""
    if session_id not in training_sessions:
        raise HTTPException(status_code=404, detail="Training session not found")

    session = training_sessions[session_id]
    game = games.get(session_id)
    opening = get_opening_by_id(session.opening_id)

    if not game or not opening:
        raise HTTPException(status_code=404, detail="Game or opening not found")

    # Check if we're past the opening moves
    if session.current_move_index >= len(opening.main_line):
        return {
            "correct": True,
            "message": "Opening complete! Well done.",
            "is_complete": True,
            "progress": 1.0,
            "state": game.state.to_dict(),
        }

    expected_move = opening.main_line[session.current_move_index]
    user_move = request.move.strip()

    # Check if move is correct (allow some flexibility)
    is_correct = user_move == expected_move.move_san

    if is_correct:
        session.correct_moves += 1
        result = game.make_move(user_move)
        session.moves_played.append(user_move)
        session.current_move_index += 1

        # Make opponent's response if available and not at end
        opponent_move = None
        opponent_move_from = None
        opponent_move_to = None
        if session.current_move_index < len(opening.main_line):
            if expected_move.common_responses:
                opponent_move = expected_move.common_responses[0]
                try:
                    move_result = game.make_move(opponent_move)
                    if move_result:
                        opponent_move_from = move_result.get('from')
                        opponent_move_to = move_result.get('to')
                except:
                    pass  # Opponent move might not be valid in all positions

        # Check if opening is complete
        is_complete = session.current_move_index >= len(opening.main_line)

        # Get next hint
        next_hint = None
        if not is_complete and session.current_move_index < len(opening.main_line):
            next_move = opening.main_line[session.current_move_index]
            next_hint = {
                "move": next_move.move_san if session.hint_level == "full" else None,
                "piece_hint": get_piece_hint(next_move.move_san) if session.hint_level == "partial" else None,
                "explanation": next_move.explanation,
                "level": session.hint_level,
            }

        return {
            "correct": True,
            "message": "Correct! " + expected_move.explanation,
            "opponent_move": opponent_move,
            "opponent_move_from": opponent_move_from,
            "opponent_move_to": opponent_move_to,
            "state": game.state.to_dict(),
            "next_hint": next_hint,
            "is_complete": is_complete,
            "progress": session.current_move_index / len(opening.main_line),
            "current_move_index": session.current_move_index,
        }
    else:
        session.incorrect_moves += 1
        return {
            "correct": False,
            "message": f"Not quite. The correct move is {expected_move.move_san}. {expected_move.explanation}",
            "expected_move": expected_move.move_san,
            "explanation": expected_move.explanation,
            "state": game.state.to_dict(),
            "progress": session.current_move_index / len(opening.main_line),
            "is_complete": False,
        }


@app.post("/api/training/{session_id}/complete")
async def complete_training(session_id: str):
    """Complete a training session and record stats."""
    if session_id not in training_sessions:
        raise HTTPException(status_code=404, detail="Training session not found")

    session = training_sessions[session_id]
    game = games.get(session_id)

    # Save the training game
    if game:
        ensure_training_games_dir()
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session.opening_id}_{timestamp}.pgn"
        filepath = TRAINING_GAMES_DIR / filename
        pgn_content = game.get_pgn()
        filepath.write_text(pgn_content)
        logger.info(f"Training game saved: {filepath}")

    # Update training stats
    stats = load_training_stats()
    progress = record_training_session(session, stats)

    # Cleanup
    del training_sessions[session_id]
    if session_id in games:
        del games[session_id]

    logger.info(f"Training session completed: {session_id}, accuracy: {session.accuracy:.0%}")
    return {
        "session_accuracy": session.accuracy,
        "correct_moves": session.correct_moves,
        "incorrect_moves": session.incorrect_moves,
        "new_mastery_level": progress.mastery_level,
        "new_hint_level": progress.current_hint_level,
        "sessions_today": stats.sessions_today,
        "daily_goal": stats.daily_goal,
    }


@app.get("/api/training/{session_id}/state")
async def get_training_state(session_id: str):
    """Get current state of a training session."""
    if session_id not in training_sessions:
        raise HTTPException(status_code=404, detail="Training session not found")

    session = training_sessions[session_id]
    game = games.get(session_id)
    opening = get_opening_by_id(session.opening_id)

    if not game or not opening:
        raise HTTPException(status_code=404, detail="Game or opening not found")

    # Get current hint
    current_hint = None
    if session.current_move_index < len(opening.main_line):
        move_info = opening.main_line[session.current_move_index]
        current_hint = {
            "move": move_info.move_san if session.hint_level == "full" else None,
            "piece_hint": get_piece_hint(move_info.move_san) if session.hint_level == "partial" else None,
            "explanation": move_info.explanation,
            "level": session.hint_level,
        }

    return {
        "session": session.to_dict(),
        "state": game.state.to_dict(),
        "current_hint": current_hint,
        "is_complete": session.current_move_index >= len(opening.main_line),
    }


class TrainingChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    fen: str
    opening_name: Optional[str] = None


@app.post("/api/training/chat")
async def training_chat(request: TrainingChatRequest):
    """Chat with AI about the current training position."""
    from anthropic import Anthropic

    client = Anthropic()

    # Build context about the position
    opening_context = f"The user is studying the {request.opening_name}. " if request.opening_name else ""

    system_prompt = f"""You are a helpful chess coach. {opening_context}
The current position (FEN): {request.fen}

Provide clear, concise explanations about chess positions, moves, and strategy.
Focus on teaching concepts rather than just giving answers.
Keep responses brief (2-3 sentences) unless a detailed explanation is needed."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": request.message}]
        )

        return {"response": response.content[0].text}
    except Exception as e:
        logger.error(f"Training chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== REVIEW MODE ENDPOINTS ====================

@app.get("/api/review/stats")
async def get_review_stats():
    """Get spaced repetition statistics."""
    manager = get_review_manager()
    return manager.get_stats()


@app.get("/api/review/due")
async def get_due_reviews(limit: int = 20, card_type: Optional[str] = None):
    """Get cards due for review."""
    manager = get_review_manager()
    due_cards = manager.get_due_cards(limit, card_type)
    return {
        "due_count": len(due_cards),
        "cards": [c.to_dict() for c in due_cards],
    }


@app.post("/api/review/start")
async def start_review(request: StartReviewRequest):
    """Start a review session."""
    manager = get_review_manager()
    due_cards = manager.get_due_cards(request.card_limit, request.card_type)

    if not due_cards:
        return {"session_id": None, "message": "No cards due for review", "total_cards": 0}

    from datetime import datetime
    session_id = f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session = ReviewSession(
        session_id=session_id,
        cards_to_review=[c.card_id for c in due_cards],
    )
    review_sessions[session_id] = session

    first_card = due_cards[0]
    logger.info(f"Review session started: {session_id} with {len(due_cards)} cards")
    return {
        "session_id": session_id,
        "total_cards": len(due_cards),
        "current_card": first_card.to_dict(),
        "progress": session.progress,
    }


@app.get("/api/review/{session_id}/current")
async def get_current_review_card(session_id: str):
    """Get the current card in a review session."""
    if session_id not in review_sessions:
        raise HTTPException(status_code=404, detail="Review session not found")

    session = review_sessions[session_id]
    if session.is_complete:
        return {
            "is_complete": True,
            "correct_count": session.correct_count,
            "incorrect_count": session.incorrect_count,
        }

    manager = get_review_manager()
    card_id = session.cards_to_review[session.current_index]
    card = manager.get_card(card_id)

    if not card:
        # Skip missing cards
        session.current_index += 1
        if session.is_complete:
            return {
                "is_complete": True,
                "correct_count": session.correct_count,
                "incorrect_count": session.incorrect_count,
            }
        return await get_current_review_card(session_id)

    return {
        "is_complete": False,
        "current_card": card.to_dict(),
        "progress": session.progress,
        "remaining": len(session.cards_to_review) - session.current_index,
    }


@app.post("/api/review/{session_id}/answer")
async def submit_review_answer(session_id: str, request: ReviewAnswerRequest):
    """Submit an answer for the current review card."""
    if session_id not in review_sessions:
        raise HTTPException(status_code=404, detail="Review session not found")

    session = review_sessions[session_id]
    if session.is_complete:
        raise HTTPException(status_code=400, detail="Session already complete")

    manager = get_review_manager()
    card_id = session.cards_to_review[session.current_index]
    card = manager.get_card(card_id)

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if answer is correct
    user_move = request.move.strip()
    is_correct = (user_move == card.expected_move or
                  user_move in card.alternative_moves)

    # Record result and update Leitner box
    updated_card = manager.record_result(card_id, is_correct)

    if is_correct:
        session.correct_count += 1
    else:
        session.incorrect_count += 1

    session.current_index += 1

    # Get next card info
    next_card = None
    if not session.is_complete:
        next_card_id = session.cards_to_review[session.current_index]
        next_card = manager.get_card(next_card_id)

    return {
        "correct": is_correct,
        "expected_move": card.expected_move,
        "explanation": card.explanation,
        "new_box": updated_card.box if updated_card else 1,
        "is_session_complete": session.is_complete,
        "next_card": next_card.to_dict() if next_card else None,
        "progress": session.progress,
        "session_stats": {
            "correct": session.correct_count,
            "incorrect": session.incorrect_count,
        }
    }


@app.post("/api/review/{session_id}/skip")
async def skip_review_card(session_id: str):
    """Skip the current review card without recording a result."""
    if session_id not in review_sessions:
        raise HTTPException(status_code=404, detail="Review session not found")

    session = review_sessions[session_id]
    if session.is_complete:
        raise HTTPException(status_code=400, detail="Session already complete")

    session.current_index += 1

    # Get next card
    next_card = None
    if not session.is_complete:
        manager = get_review_manager()
        next_card_id = session.cards_to_review[session.current_index]
        next_card = manager.get_card(next_card_id)

    return {
        "skipped": True,
        "is_session_complete": session.is_complete,
        "next_card": next_card.to_dict() if next_card else None,
        "progress": session.progress,
    }


@app.post("/api/review/{session_id}/complete")
async def complete_review_session(session_id: str):
    """Complete and cleanup a review session."""
    if session_id not in review_sessions:
        raise HTTPException(status_code=404, detail="Review session not found")

    session = review_sessions[session_id]
    total_reviewed = session.correct_count + session.incorrect_count

    result = {
        "correct_count": session.correct_count,
        "incorrect_count": session.incorrect_count,
        "total_reviewed": total_reviewed,
        "accuracy": session.correct_count / max(1, total_reviewed),
    }

    del review_sessions[session_id]
    logger.info(f"Review session completed: {session_id}, {result['correct_count']}/{total_reviewed} correct")
    return result


@app.post("/api/review/generate-opening-cards/{opening_id}")
async def generate_opening_cards(opening_id: str):
    """Generate review cards for an opening."""
    opening = get_opening_by_id(opening_id)
    if not opening:
        raise HTTPException(status_code=404, detail="Opening not found")

    card_ids = generate_opening_review_cards(opening_id)
    return {
        "opening_id": opening_id,
        "cards_created": len(card_ids),
        "card_ids": card_ids,
    }


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

    # Helper to get current game (allows HTTP endpoints to replace the game)
    def get_game() -> ChessGame:
        if game_id not in games:
            games[game_id] = ChessGame()
        return games[game_id]

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            logger.info(f"Received message: {msg_type}")

            # Get fresh game reference for each message (allows load game to work)
            game = get_game()

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
                # Player makes a move (from drag-drop or click-to-move)
                move_str = data.get("move", "")

                # Analyze the move BEFORE making it for blunder detection
                blunder_feedback = None
                board_before = game.state.board.copy()

                result = game.make_move(move_str)

                await websocket.send_json({
                    "type": "move_result",
                    "result": result
                })

                if result["success"]:
                    # Check if the move was a blunder/mistake (for tutoring)
                    blunder_feedback = await analyze_player_move(board_before, result['move'])
                    save_game_pgn(game, "current_game.pgn")

                    # Check for game over
                    if game.state.board.is_game_over():
                        await handle_game_over(websocket, game)
                        return

                    # If it's now AI's turn, make AI move
                    if game.is_ai_turn():
                        player_context = f"I played {result['move']}."
                        if blunder_feedback:
                            player_context += f" [TUTOR: {blunder_feedback}]"
                        await handle_ai_turn(websocket, game, player_context, blunder_feedback=blunder_feedback)

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
        current_game = games.get(game_id)
        if current_game and current_game.state.board.move_stack:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_game_pgn(current_game, f"game_{timestamp}_session.pgn")
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
    logger.info(f"[PARSE] \"{message}\" -> {move_result}")
    if move_result:
        # Analyze the move BEFORE making it for blunder detection
        blunder_feedback = None
        board_before = game.state.board.copy()

        result = game.make_move(move_result)
        if result["success"]:
            logger.info(f"[PLAYER MOVE] {result['move']}")
            save_game_pgn(game, "current_game.pgn")

            # Check if the move was a blunder/mistake (for tutoring)
            blunder_feedback = await analyze_player_move(board_before, result['move'])

            await websocket.send_json({
                "type": "move_result",
                "result": result
            })

            # Check for game over after player's move
            if game.state.board.is_game_over():
                await handle_game_over(websocket, game)
                return

            # AI responds and moves, include blunder feedback
            if game.is_ai_turn():
                player_context = f"I played {result['move']}."
                if blunder_feedback:
                    player_context += f" [TUTOR: {blunder_feedback}]"
                await handle_ai_turn(websocket, game, player_context, blunder_feedback=blunder_feedback)
            return
        else:
            # Move was parsed but invalid - tell user why
            error_msg = result.get("error", "Invalid move")
            legal_moves = game.get_legal_moves()
            logger.info(f"[INVALID MOVE] {move_result}: {error_msg}")

            # Check if it's not their turn
            if not game.is_ai_turn():
                # It's the player's turn but move was illegal
                await websocket.send_json({
                    "type": "ai_response",
                    "message": f"That move isn't legal right now. {error_msg}",
                    "move": None
                })
            else:
                # It's AI's turn - player trying to move out of turn
                await websocket.send_json({
                    "type": "ai_response",
                    "message": "Hold on - it's my turn to move!",
                    "move": None
                })
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

    # Check if this is a question/request (not a move attempt)
    question_words = ['explain', 'why', 'what', 'how', 'analyze', 'analyse', 'analysis',
                      'help', 'hint', 'tell', 'show', 'can we', 'can you', 'could you', '?']
    is_question = any(word in message_lower for word in question_words)

    if is_question:
        # This is a question - send to AI for tutoring
        await handle_ai_turn(websocket, game, message)
        return

    # Not a recognized move or command - check if it looks like they're trying to make a move
    move_keywords = ['move', 'play', 'take', 'capture', 'go', 'push']
    looks_like_move_attempt = any(kw in message_lower for kw in move_keywords)

    if looks_like_move_attempt and not game.is_ai_turn():
        # They seem to be trying to make a move but we couldn't parse it
        legal_moves = game.get_legal_moves()[:10]
        await websocket.send_json({
            "type": "ai_response",
            "message": f"I didn't catch that move. Try saying it like 'e4' or 'knight to f3'. Some legal moves: {', '.join(legal_moves)}",
            "move": None
        })
        return

    # Send to AI for conversation (questions, chat, etc.)
    await handle_ai_turn(websocket, game, message)


def try_parse_player_move(text: str, game: ChessGame) -> Optional[str]:
    """
    Try to extract a chess move from player's spoken/typed text.
    Returns the move string if found, None otherwise.
    """
    import re
    text_lower = text.lower().strip()

    # Handle spoken numbers FIRST: "e four" -> "e 4", "knight f three" -> "knight f 3"
    number_words = {"one": "1", "two": "2", "three": "3", "four": "4",
                    "five": "5", "six": "6", "seven": "7", "eight": "8"}
    normalized = text_lower
    for word, digit in number_words.items():
        normalized = re.sub(rf'\b{word}\b', digit, normalized)

    # Remove extra spaces: "e 4" -> "e4", "d 4" -> "d4"
    normalized = re.sub(r'([a-h])\s+([1-8])', r'\1\2', normalized)

    # Handle "takes on" -> "takes" (common speech pattern)
    normalized = re.sub(r'takes?\s+on\s+', 'takes ', normalized)
    normalized = re.sub(r'capture\s+on\s+', 'captures ', normalized)

    # Handle "on d4" -> "d4" (remove standalone "on" before square)
    normalized = re.sub(r'\bon\s+([a-h][1-8])\b', r'\1', normalized)

    # Handle castling - various spoken forms
    castling_kingside = ["castle kingside", "castle king side", "short castle",
                         "castles kingside", "castle short", "kingside castle",
                         "castle king", "oh oh", "o-o"]
    castling_queenside = ["castle queenside", "castle queen side", "long castle",
                          "castles queenside", "castle long", "queenside castle",
                          "castle queen", "oh oh oh", "o-o-o"]

    if any(phrase in normalized for phrase in castling_kingside):
        return "O-O"
    if any(phrase in normalized for phrase in castling_queenside):
        return "O-O-O"

    # Piece name map for spoken moves
    piece_map = {
        "knight": "N", "bishop": "B", "rook": "R",
        "queen": "Q", "king": "K", "pawn": ""
    }

    # Check for capture moves: "queen takes d4", "knight captures e5"
    capture_pattern = r'\b(knight|bishop|rook|queen|king|pawn)\s+(?:takes?|captures?|x)\s*([a-h])([1-8])\b'
    match = re.search(capture_pattern, normalized)
    if match:
        piece = piece_map.get(match.group(1), "")
        file = match.group(2)
        rank = match.group(3)
        return f"{piece}x{file}{rank}"

    # Check for regular moves: "queen d4", "knight to f3", "bishop e5"
    move_pattern = r'\b(knight|bishop|rook|queen|king|pawn)\s+(?:to\s+)?([a-h])([1-8])\b'
    match = re.search(move_pattern, normalized)
    if match:
        piece = piece_map.get(match.group(1), "")
        file = match.group(2)
        rank = match.group(3)
        return f"{piece}{file}{rank}"

    # Standard algebraic notation: "Qxd4", "Nf3", "e4"
    san_pattern = r'\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b'
    match = re.search(san_pattern, normalized, re.IGNORECASE)
    if match:
        move = match.group(1)
        # Uppercase piece letters
        if len(move) > 2 and move[0].lower() in 'kqrbn':
            move = move[0].upper() + move[1:]
        return move

    # Simple pawn move: just "d4" or "e4"
    simple_pattern = r'\b([a-h][1-8])\b'
    match = re.search(simple_pattern, normalized)
    if match:
        return match.group(1)

    return None


async def analyze_player_move(board_before: chess.Board, move_san: str) -> Optional[str]:
    """
    Analyze the player's move for blunders, mistakes, and teaching opportunities.

    Returns feedback string if there's something to teach, None otherwise.
    """
    engine = get_engine()
    if not engine.is_running():
        return None

    try:
        # Parse the move
        move = board_before.parse_san(move_san)

        # Get evaluation before the move
        result_before = engine.get_best_move(board_before)
        if not result_before:
            return None

        best_move, analysis_before = result_before
        eval_before = float(analysis_before.get('score', 0))
        best_move_san = analysis_before.get('move')

        # Make the move on a copy
        board_after = board_before.copy()
        board_after.push(move)

        # Get evaluation after the move
        result_after = engine.get_best_move(board_after)
        if not result_after:
            return None

        _, analysis_after = result_after
        eval_after = float(analysis_after.get('score', 0))

        # Calculate loss from player's perspective
        is_white = board_before.turn == chess.WHITE
        if is_white:
            eval_loss = (eval_before - eval_after) * 100  # Centipawns
        else:
            eval_loss = ((-eval_before) - (-eval_after)) * 100

        # Classify the move
        played_is_best = best_move_san and move_san == best_move_san

        # Log the analysis
        logger.info(f"[MOVE ANALYSIS] {move_san}: eval_before={eval_before:.2f}, eval_after={eval_after:.2f}, "
                   f"loss={eval_loss:.0f}cp, best={best_move_san}")

        # Generate feedback based on severity
        if eval_loss > 200:  # Blunder (>2 pawns)
            feedback = f"That was a blunder! You lost about {eval_loss/100:.1f} pawns of advantage. "
            if best_move_san and not played_is_best:
                feedback += f"{best_move_san} was much better."

            # Check for tactical issues
            tactics = analyze_tactics(board_after)
            critical = [t for t in tactics if t.severity == 'critical']
            if critical:
                feedback += f" Watch out: {critical[0].description}"

            # Create a review card for this blunder (spaced repetition)
            try:
                manager = get_review_manager()
                explanation = f"You played {move_san} but {best_move_san} was better. {feedback}"
                move_num = len(board_before.move_stack) // 2 + 1
                manager.create_blunder_card(
                    fen=board_before.fen(),
                    best_move=best_move_san,
                    source_game="current_game.pgn",
                    explanation=explanation,
                    move_number=move_num
                )
                logger.info(f"[REVIEW] Created blunder review card for position")
            except Exception as e:
                logger.error(f"Failed to create blunder card: {e}")

            return feedback

        elif eval_loss > 100:  # Mistake (>1 pawn)
            feedback = f"That's a mistake - you lost about {eval_loss/100:.1f} pawns. "
            if best_move_san and not played_is_best:
                feedback += f"Consider {best_move_san} next time."
            return feedback

        elif eval_loss > 50:  # Inaccuracy (>0.5 pawns)
            if best_move_san and not played_is_best:
                return f"Small inaccuracy. {best_move_san} was slightly better."

        # Check for positional issues even if not a clear mistake
        tactics = analyze_tactics(board_after)
        warnings = [t for t in tactics if t.severity in ['warning', 'critical']]

        # Warn about hanging pieces or threats created against player
        for tactic in warnings[:1]:  # Just the first warning
            if 'hanging' in tactic.type.lower():
                return f"Be careful! {tactic.description}"

        return None

    except Exception as e:
        logger.error(f"Move analysis error: {e}")
        return None


async def handle_ai_turn(websocket: WebSocket, game: ChessGame, player_message: str, blunder_feedback: Optional[str] = None):
    """
    Handle AI's turn using Stockfish for moves, Ollama for commentary.

    Architecture:
    - Stockfish: Generates strong, tactically sound moves
    - Ollama: Explains the move using Stockfish's analysis
    """
    import asyncio

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
        move_context = None
        last_move = None
        board_before_move = None
        detailed_thinking = []

        # If it's AI's turn, use Stockfish for the move
        if is_ai_turn:
            engine = get_engine()

            if engine.is_running():
                # Enhanced thinking: Analyze position first
                logger.info("[AI THINKING] Analyzing position...")

                # Get tactical analysis
                tactics = analyze_tactics(game.state.board)
                if tactics:
                    for tactic in tactics[:3]:
                        logger.info(f"[TACTICS] {tactic.type}: {tactic.description}")
                        detailed_thinking.append(f"Tactical: {tactic.description}")

                # Small delay to simulate thinking (makes AI feel more natural)
                await asyncio.sleep(0.5)

                # Get Stockfish's analysis with multiple candidate moves
                result = engine.get_best_move(game.state.board)

                if result:
                    move, analysis = result
                    engine_analysis = analysis
                    last_move = move

                    # Enhanced logging: Show thinking process
                    logger.info(f"[AI THINKING] Evaluating position...")
                    logger.info(f"[STOCKFISH] Best move: {analysis['move']} (eval: {analysis['score']})")
                    logger.info(f"[STOCKFISH] Search depth: {analysis['depth']}")
                    logger.info(f"[STOCKFISH] Principal variation: {' '.join(analysis['pv'][:5])}")

                    # Log what the AI is "considering"
                    pv = analysis.get('pv', [])
                    if len(pv) >= 2:
                        logger.info(f"[AI THINKING] If I play {pv[0]}, opponent likely responds {pv[1]}...")
                        detailed_thinking.append(f"Considering {pv[0]}, anticipating {pv[1]}")

                    # Check what threats are being created
                    board_copy = game.state.board.copy()
                    board_copy.push(move)
                    post_move_tactics = analyze_tactics(board_copy)
                    new_threats = [t for t in post_move_tactics if t.severity in ['warning', 'critical']]
                    if new_threats:
                        for threat in new_threats[:2]:
                            logger.info(f"[AI THINKING] This creates: {threat.description}")
                            detailed_thinking.append(f"Creates threat: {threat.description}")

                    # Save board state BEFORE making the move (for accurate commentary)
                    board_before_move = game.state.board.copy()

                    # Get move context BEFORE making the move
                    move_context = engine.get_move_explanation_context(game.state.board, move)

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
                        move_context = ai_move
                        logger.info(f"[FALLBACK MOVE] {ai_move}")
                        save_game_pgn(game, "current_game.pgn")

        # Generate commentary - uses Stockfish analysis, NOT LLM hallucination
        response = await generate_move_commentary(
            game, player_message, ai_move, engine_analysis, move_context, is_ai_turn,
            last_move=last_move, board_before_move=board_before_move
        )

        # Store in conversation history
        game.add_conversation("user", player_message)
        game.add_conversation("assistant", response)

        # Extract move squares for replay feature
        move_from = None
        move_to = None
        if last_move:
            move_from = chess.square_name(last_move.from_square)
            move_to = chess.square_name(last_move.to_square)

        # If there's blunder feedback, prepend it to the response
        full_response = response
        if blunder_feedback:
            full_response = f"{blunder_feedback} Now, {response}"
            logger.info(f"[TUTOR] {blunder_feedback}")

        logger.info(f"[RESPONSE] Sending ai_response: move={ai_move}, message={full_response[:50]}...")
        await websocket.send_json({
            "type": "ai_response",
            "message": full_response,
            "move": ai_move,
            "move_from": move_from,
            "move_to": move_to,
            "blunder_feedback": blunder_feedback,
            "state": game.state.to_dict()
        })

        # Check for game over
        if game.state.board.is_game_over():
            await handle_game_over(websocket, game)

    except Exception as e:
        logger.error(f"AI turn error: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
    move_context: Optional[str],
    is_ai_turn: bool,
    last_move: Optional[chess.Move] = None,
    board_before_move: Optional[chess.Board] = None
) -> str:
    """
    Generate natural language commentary for a move or respond to questions.

    For moves: Uses Stockfish analysis + board state for ACCURATE commentary (no LLM hallucination)
    For questions: Uses Ollama with structured Stockfish analysis
    """
    # Check if this is a question (tutor mode)
    is_question = any(word in player_message.lower() for word in
                      ['why', 'what', 'how', 'explain', 'help', 'hint', 'analyze', 'analyse',
                       'analysis', 'can we', 'can you', 'could you', 'review', 'look at', '?'])

    if is_question:
        # Tutor mode - get fresh analysis and give detailed explanation
        engine = get_engine()
        stockfish_analysis = {}

        if engine.is_running():
            stockfish_analysis = engine.evaluate_position(game.state.board)

        if ollama_client:
            response = await ollama_client.answer_question(
                question=player_message,
                position_fen=game.state.board.fen(),
                move_history=game.get_formatted_history(),
                stockfish_analysis=stockfish_analysis,
                conversation_history=game.get_conversation_history()[-4:],
            )
            logger.info(f"[TUTOR] {response[:100]}...")
            return response
        else:
            # No Ollama - return Stockfish analysis directly
            if stockfish_analysis.get('best_moves'):
                lines = [f"Position evaluation: {stockfish_analysis.get('score', '0.0')}"]
                for i, mv in enumerate(stockfish_analysis.get('best_moves', [])[:3], 1):
                    lines.append(f"{i}. {mv['move']} (eval: {mv['score']})")
                return " | ".join(lines)
            return "Position is roughly equal."

    elif ai_move and engine_analysis and board_before_move and last_move:
        # Just made a move - use ACCURATE Stockfish-based commentary (no LLM)
        engine = get_engine()
        if engine.is_running():
            commentary = engine.generate_move_commentary(board_before_move, last_move, engine_analysis)
            logger.info(f"[COMMENT] {commentary}")
            return commentary
        else:
            return f"{ai_move}."

    elif ai_move:
        # Move without full analysis
        return f"{ai_move}."

    else:
        # No move, just acknowledge
        return "Your move."


async def handle_game_over(websocket: WebSocket, game: ChessGame):
    """Handle game over - send result and stats to frontend."""
    from datetime import datetime
    board = game.state.board
    player_color = game.state.player_color

    # Determine result
    result_str = board.result()  # "1-0", "0-1", "1/2-1/2"
    is_checkmate = board.is_checkmate()
    is_stalemate = board.is_stalemate()
    is_draw = board.is_game_over() and not is_checkmate

    # Determine who won from player's perspective
    if result_str == "1-0":
        player_result = "win" if player_color == "white" else "loss"
        winner = "White"
    elif result_str == "0-1":
        player_result = "win" if player_color == "black" else "loss"
        winner = "Black"
    else:
        player_result = "draw"
        winner = None

    # Generate result message
    if is_checkmate:
        if player_result == "win":
            message = "Checkmate! Congratulations, you won!"
        else:
            message = "Checkmate! I got you this time. Good game!"
    elif is_stalemate:
        message = "Stalemate! The game is a draw."
    elif is_draw:
        reason = ""
        if board.is_insufficient_material():
            reason = "insufficient material"
        elif board.is_fifty_moves():
            reason = "fifty-move rule"
        elif board.is_repetition():
            reason = "threefold repetition"
        message = f"Draw by {reason}!" if reason else "The game is a draw!"
    else:
        message = "Game over!"

    logger.info(f"[GAME OVER] {result_str} - Player {player_result}")

    # Send game_over event to frontend
    await websocket.send_json({
        "type": "game_over",
        "result": player_result,
        "result_notation": result_str,
        "winner": winner,
        "is_checkmate": is_checkmate,
        "is_stalemate": is_stalemate,
        "is_draw": is_draw,
        "message": message,
        "moves_count": len(board.move_stack),
        "player_color": player_color,
        "state": game.state.to_dict()
    })


def run_server(host: str = "127.0.0.1", port: int = 8766, open_browser: bool = True):
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
