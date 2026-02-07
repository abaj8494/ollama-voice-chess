"""
Training session management and progress tracking.
Handles training mode for chess openings with progressive hint reduction.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

TRAINING_STATS_FILE = Path(__file__).parent.parent / "data" / "training_stats.json"
TRAINING_GAMES_DIR = Path(__file__).parent.parent / "training_games"


class HintLevel(Enum):
    """Levels of hints provided during training."""
    FULL = "full"           # Show the exact move before user plays
    PARTIAL = "partial"     # Show the piece type but not the destination
    MINIMAL = "minimal"     # Only indicate a move is expected
    NONE = "none"           # No hints - user is tested


@dataclass
class TrainingProgress:
    """Progress for a specific opening."""
    opening_id: str
    sessions_completed: int = 0
    moves_practiced: int = 0
    accuracy_history: List[float] = field(default_factory=list)
    last_practiced: Optional[str] = None  # ISO timestamp
    current_hint_level: str = "full"
    mastered_moves: List[int] = field(default_factory=list)  # Indices of mastered moves

    @property
    def average_accuracy(self) -> float:
        """Get average accuracy from recent sessions (last 10)."""
        if not self.accuracy_history:
            return 0.0
        recent = self.accuracy_history[-10:]
        return sum(recent) / len(recent)

    @property
    def mastery_level(self) -> str:
        """Determine mastery based on accuracy and sessions."""
        acc = self.average_accuracy
        sessions = self.sessions_completed
        if acc >= 0.9 and sessions >= 10:
            return "mastered"
        elif acc >= 0.7 and sessions >= 5:
            return "proficient"
        elif acc >= 0.5 and sessions >= 2:
            return "learning"
        else:
            return "beginner"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opening_id": self.opening_id,
            "sessions_completed": self.sessions_completed,
            "moves_practiced": self.moves_practiced,
            "accuracy_history": self.accuracy_history,
            "last_practiced": self.last_practiced,
            "current_hint_level": self.current_hint_level,
            "mastered_moves": self.mastered_moves,
            "average_accuracy": self.average_accuracy,
            "mastery_level": self.mastery_level,
        }


@dataclass
class TrainingSession:
    """Active training session state."""
    session_id: str
    opening_id: str
    player_color: str
    current_move_index: int = 0
    moves_played: List[str] = field(default_factory=list)
    correct_moves: int = 0
    incorrect_moves: int = 0
    hint_level: str = "full"
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    opponent_first_move: Optional[str] = None  # For Black openings

    @property
    def accuracy(self) -> float:
        """Calculate current session accuracy."""
        total = self.correct_moves + self.incorrect_moves
        if total == 0:
            return 1.0
        return self.correct_moves / total

    @property
    def total_attempts(self) -> int:
        return self.correct_moves + self.incorrect_moves

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "opening_id": self.opening_id,
            "player_color": self.player_color,
            "current_move_index": self.current_move_index,
            "moves_played": self.moves_played,
            "correct_moves": self.correct_moves,
            "incorrect_moves": self.incorrect_moves,
            "hint_level": self.hint_level,
            "accuracy": self.accuracy,
            "started_at": self.started_at,
            "total_attempts": self.total_attempts,
        }


@dataclass
class TrainingStats:
    """Overall training statistics."""
    total_sessions: int = 0
    total_moves_practiced: int = 0
    sessions_today: int = 0
    last_session_date: Optional[str] = None
    opening_progress: Dict[str, TrainingProgress] = field(default_factory=dict)
    daily_goal: int = 5  # Suggested games per day

    def get_opening_progress(self, opening_id: str) -> TrainingProgress:
        """Get or create progress for an opening."""
        if opening_id not in self.opening_progress:
            self.opening_progress[opening_id] = TrainingProgress(opening_id=opening_id)
        return self.opening_progress[opening_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "total_moves_practiced": self.total_moves_practiced,
            "sessions_today": self.sessions_today,
            "last_session_date": self.last_session_date,
            "daily_goal": self.daily_goal,
            "opening_progress": {
                op_id: p.to_dict()
                for op_id, p in self.opening_progress.items()
            },
        }


def load_training_stats() -> TrainingStats:
    """Load training statistics from file."""
    TRAINING_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if TRAINING_STATS_FILE.exists():
        try:
            with open(TRAINING_STATS_FILE, 'r') as f:
                data = json.load(f)

            stats = TrainingStats(
                total_sessions=data.get("total_sessions", 0),
                total_moves_practiced=data.get("total_moves_practiced", 0),
                sessions_today=data.get("sessions_today", 0),
                last_session_date=data.get("last_session_date"),
                daily_goal=data.get("daily_goal", 5),
            )

            # Check if we need to reset daily counter
            today = datetime.now().date().isoformat()
            if stats.last_session_date != today:
                stats.sessions_today = 0

            # Load opening progress
            for op_id, op_data in data.get("opening_progress", {}).items():
                stats.opening_progress[op_id] = TrainingProgress(
                    opening_id=op_id,
                    sessions_completed=op_data.get("sessions_completed", 0),
                    moves_practiced=op_data.get("moves_practiced", 0),
                    accuracy_history=op_data.get("accuracy_history", []),
                    last_practiced=op_data.get("last_practiced"),
                    current_hint_level=op_data.get("current_hint_level", "full"),
                    mastered_moves=op_data.get("mastered_moves", []),
                )

            return stats
        except Exception as e:
            print(f"Error loading training stats: {e}")

    return TrainingStats()


def save_training_stats(stats: TrainingStats):
    """Save training statistics to file."""
    TRAINING_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "total_sessions": stats.total_sessions,
        "total_moves_practiced": stats.total_moves_practiced,
        "sessions_today": stats.sessions_today,
        "last_session_date": stats.last_session_date,
        "daily_goal": stats.daily_goal,
        "opening_progress": {
            op_id: {
                "sessions_completed": p.sessions_completed,
                "moves_practiced": p.moves_practiced,
                "accuracy_history": p.accuracy_history[-50:],  # Keep last 50
                "last_practiced": p.last_practiced,
                "current_hint_level": p.current_hint_level,
                "mastered_moves": p.mastered_moves,
            }
            for op_id, p in stats.opening_progress.items()
        },
    }

    with open(TRAINING_STATS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def calculate_hint_level(progress: TrainingProgress) -> str:
    """Determine appropriate hint level based on progress."""
    acc = progress.average_accuracy
    sessions = progress.sessions_completed

    # Progressive hint reduction
    if sessions < 2:
        return "full"
    elif sessions < 5 or acc < 0.5:
        return "partial"
    elif sessions < 10 or acc < 0.7:
        return "minimal"
    elif acc >= 0.9:
        return "none"
    else:
        return "minimal"


def get_piece_hint(move_san: str) -> str:
    """Extract piece hint from a SAN move for partial hints."""
    piece_names = {
        "K": "King",
        "Q": "Queen",
        "R": "Rook",
        "B": "Bishop",
        "N": "Knight",
    }

    if move_san in ["O-O", "O-O-O"]:
        return "Castle"
    elif move_san[0] in piece_names:
        return f"Move your {piece_names[move_san[0]]}"
    else:
        # Pawn move
        return "Move a pawn"


def record_training_session(
    session: TrainingSession,
    stats: TrainingStats
) -> TrainingProgress:
    """Record a completed training session and update stats."""
    progress = stats.get_opening_progress(session.opening_id)

    # Update progress
    progress.sessions_completed += 1
    progress.moves_practiced += len(session.moves_played)
    progress.accuracy_history.append(session.accuracy)
    progress.last_practiced = datetime.now().isoformat()
    progress.current_hint_level = calculate_hint_level(progress)

    # Update overall stats
    stats.total_sessions += 1
    stats.total_moves_practiced += len(session.moves_played)
    stats.sessions_today += 1
    stats.last_session_date = datetime.now().date().isoformat()

    # Save to disk
    save_training_stats(stats)

    return progress


def ensure_training_games_dir():
    """Ensure the training games directory exists."""
    TRAINING_GAMES_DIR.mkdir(parents=True, exist_ok=True)
    return TRAINING_GAMES_DIR
