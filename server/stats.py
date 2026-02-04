"""
Player statistics and adaptive difficulty system.

Tracks game history and adjusts Stockfish difficulty based on performance.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

STATS_FILE = Path(__file__).parent.parent / "data" / "player_stats.json"
DEFAULT_DIFFICULTY = 10  # Stockfish skill 0-20, 10 is intermediate
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 20


def ensure_data_dir():
    """Ensure the data directory exists."""
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_stats() -> dict:
    """Load player statistics from file."""
    ensure_data_dir()
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load stats: {e}")

    # Return default stats
    return {
        "games_played": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "current_difficulty": DEFAULT_DIFFICULTY,
        "difficulty_history": [],
        "game_history": [],
    }


def save_stats(stats: dict):
    """Save player statistics to file."""
    ensure_data_dir()
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except IOError as e:
        logger.error(f"Failed to save stats: {e}")


def record_game(
    result: str,  # "win", "loss", "draw"
    player_color: str,
    moves_count: int,
    final_eval: Optional[float] = None,
    game_name: Optional[str] = None,
    pgn_file: Optional[str] = None,
):
    """
    Record a completed game and adjust difficulty.

    Args:
        result: "win" (player won), "loss" (AI won), or "draw"
        player_color: "white" or "black"
        moves_count: Total number of half-moves in the game
        final_eval: Final position evaluation (from white's perspective)
        game_name: Optional name for the game
        pgn_file: Path to saved PGN file
    """
    stats = load_stats()

    stats["games_played"] += 1
    if result == "win":
        stats["wins"] += 1
    elif result == "loss":
        stats["losses"] += 1
    else:
        stats["draws"] += 1

    # Record game details
    game_record = {
        "date": datetime.now().isoformat(),
        "result": result,
        "player_color": player_color,
        "moves": moves_count,
        "difficulty": stats["current_difficulty"],
        "final_eval": final_eval,
        "name": game_name,
        "pgn_file": pgn_file,
    }
    stats["game_history"].append(game_record)

    # Keep only last 50 games in history
    if len(stats["game_history"]) > 50:
        stats["game_history"] = stats["game_history"][-50:]

    # Calculate new difficulty
    old_difficulty = stats["current_difficulty"]
    new_difficulty = calculate_adaptive_difficulty(stats, result, moves_count, final_eval)

    if new_difficulty != old_difficulty:
        stats["current_difficulty"] = new_difficulty
        stats["difficulty_history"].append({
            "date": datetime.now().isoformat(),
            "old": old_difficulty,
            "new": new_difficulty,
            "reason": get_adjustment_reason(result, moves_count, final_eval),
        })
        logger.info(f"Difficulty adjusted: {old_difficulty} -> {new_difficulty}")

    save_stats(stats)
    return stats


def calculate_adaptive_difficulty(
    stats: dict,
    last_result: str,
    moves_count: int,
    final_eval: Optional[float]
) -> int:
    """
    Calculate new difficulty based on recent performance.

    Algorithm:
    - If player wins: increase difficulty by 1-2
    - If player loses quickly (< 30 moves) or badly (eval > 5): decrease by 2
    - If player loses after a fight (> 50 moves, close eval): keep or slight decrease
    - If draw: slight adjustment toward middle

    Also considers win rate over last 5-10 games.
    """
    current = stats["current_difficulty"]

    # Get recent games (last 5)
    recent = stats["game_history"][-5:] if stats["game_history"] else []
    recent_wins = sum(1 for g in recent if g["result"] == "win")
    recent_losses = sum(1 for g in recent if g["result"] == "loss")

    adjustment = 0

    if last_result == "win":
        # Player won - increase difficulty
        if recent_wins >= 3:
            # Winning streak - bigger increase
            adjustment = 2
        else:
            adjustment = 1

    elif last_result == "loss":
        # Player lost - analyze how
        quick_loss = moves_count < 30  # Lost in under 15 full moves
        crushing_loss = final_eval is not None and abs(final_eval) > 5

        if quick_loss or crushing_loss:
            # Got crushed - significant decrease
            adjustment = -2
        elif moves_count < 50:
            # Moderate loss
            adjustment = -1
        else:
            # Long game, fought well - small or no decrease
            if recent_losses >= 3:
                adjustment = -1
            else:
                adjustment = 0

    else:  # Draw
        # Draws suggest appropriate difficulty
        # Slight adjustment toward win rate balance
        if recent_wins > recent_losses:
            adjustment = 1  # Player doing well, slight increase
        elif recent_losses > recent_wins:
            adjustment = -1  # Player struggling, slight decrease

    # Apply adjustment with bounds
    new_difficulty = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, current + adjustment))

    return new_difficulty


def get_adjustment_reason(result: str, moves_count: int, final_eval: Optional[float]) -> str:
    """Get human-readable reason for difficulty adjustment."""
    if result == "win":
        return "Player victory"
    elif result == "loss":
        if moves_count < 30:
            return "Quick loss - reducing difficulty"
        elif final_eval and abs(final_eval) > 5:
            return "Decisive loss - reducing difficulty"
        else:
            return "Loss after good fight"
    else:
        return "Draw - balanced difficulty"


def get_current_difficulty() -> int:
    """Get the current difficulty setting."""
    stats = load_stats()
    return stats.get("current_difficulty", DEFAULT_DIFFICULTY)


def set_difficulty(level: int) -> int:
    """Manually set difficulty level."""
    level = max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, level))
    stats = load_stats()
    old = stats["current_difficulty"]
    stats["current_difficulty"] = level
    if old != level:
        stats["difficulty_history"].append({
            "date": datetime.now().isoformat(),
            "old": old,
            "new": level,
            "reason": "Manual adjustment",
        })
    save_stats(stats)
    return level


def get_stats_summary() -> dict:
    """Get a summary of player statistics."""
    stats = load_stats()

    games = stats["games_played"]
    if games == 0:
        win_rate = 0
    else:
        win_rate = stats["wins"] / games

    return {
        "games_played": games,
        "wins": stats["wins"],
        "losses": stats["losses"],
        "draws": stats["draws"],
        "win_rate": round(win_rate * 100, 1),
        "current_difficulty": stats["current_difficulty"],
        "difficulty_name": get_difficulty_name(stats["current_difficulty"]),
    }


def get_difficulty_name(level: int) -> str:
    """Get human-readable name for difficulty level."""
    if level <= 3:
        return "Beginner"
    elif level <= 6:
        return "Easy"
    elif level <= 10:
        return "Intermediate"
    elif level <= 14:
        return "Advanced"
    elif level <= 17:
        return "Expert"
    else:
        return "Master"


def get_game_history(limit: int = 10) -> list:
    """Get recent game history."""
    stats = load_stats()
    return stats["game_history"][-limit:][::-1]  # Most recent first
