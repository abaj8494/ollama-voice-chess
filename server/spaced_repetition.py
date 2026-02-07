"""
Spaced repetition system using the Leitner method.
Manages review cards for opening sequences, blunder positions, and tactical patterns.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid
from pathlib import Path

REVIEW_DATA_FILE = Path(__file__).parent.parent / "data" / "review_cards.json"


class CardType(Enum):
    """Types of review cards."""
    OPENING_SEQUENCE = "opening_sequence"   # Sequence of opening moves
    BLUNDER_POSITION = "blunder_position"   # Position where user blundered
    TACTICAL_PATTERN = "tactical_pattern"   # Tactical motif to practice
    CRITICAL_POSITION = "critical_position" # Key position from a game


# Leitner box intervals (in days)
# Box 1: Daily, Box 6: Monthly (mastered)
LEITNER_INTERVALS = {
    1: 1,    # Box 1: Review daily
    2: 2,    # Box 2: Every 2 days
    3: 4,    # Box 3: Every 4 days
    4: 7,    # Box 4: Weekly
    5: 14,   # Box 5: Every 2 weeks
    6: 30,   # Box 6: Monthly (mastered)
}


@dataclass
class ReviewCard:
    """A single review card for spaced repetition."""
    card_id: str
    card_type: str  # From CardType enum

    # Position info
    fen: str                              # Position to review
    expected_move: str                     # Correct move (SAN)
    alternative_moves: List[str] = field(default_factory=list)  # Also acceptable

    # Context
    opening_id: Optional[str] = None       # For opening cards
    source_game: Optional[str] = None      # PGN file for blunder cards
    move_number: int = 0                   # Move number in opening/game

    # Explanation
    explanation: str = ""                  # Why this is the right move
    tactical_theme: Optional[str] = None   # e.g., "pin", "fork"

    # Leitner system
    box: int = 1                           # Current Leitner box (1-6)
    next_review: str = ""                  # ISO timestamp
    last_reviewed: Optional[str] = None
    review_count: int = 0
    correct_streak: int = 0

    # Stats
    times_correct: int = 0
    times_incorrect: int = 0

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def mastery_level(self) -> float:
        """0.0 to 1.0 based on box and accuracy."""
        if self.review_count == 0:
            return 0.0
        accuracy = self.times_correct / self.review_count
        box_weight = (self.box - 1) / 5  # 0.0 to 1.0
        return (accuracy + box_weight) / 2

    @property
    def is_due(self) -> bool:
        """Check if card is due for review."""
        if not self.next_review:
            return True
        try:
            review_time = datetime.fromisoformat(self.next_review)
            return datetime.now() >= review_time
        except ValueError:
            return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_type": self.card_type,
            "fen": self.fen,
            "expected_move": self.expected_move,
            "alternative_moves": self.alternative_moves,
            "opening_id": self.opening_id,
            "source_game": self.source_game,
            "move_number": self.move_number,
            "explanation": self.explanation,
            "tactical_theme": self.tactical_theme,
            "box": self.box,
            "next_review": self.next_review,
            "last_reviewed": self.last_reviewed,
            "review_count": self.review_count,
            "correct_streak": self.correct_streak,
            "times_correct": self.times_correct,
            "times_incorrect": self.times_incorrect,
            "created_at": self.created_at,
            "mastery_level": self.mastery_level,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ReviewCard":
        return cls(
            card_id=data["card_id"],
            card_type=data["card_type"],
            fen=data["fen"],
            expected_move=data["expected_move"],
            alternative_moves=data.get("alternative_moves", []),
            opening_id=data.get("opening_id"),
            source_game=data.get("source_game"),
            move_number=data.get("move_number", 0),
            explanation=data.get("explanation", ""),
            tactical_theme=data.get("tactical_theme"),
            box=data.get("box", 1),
            next_review=data.get("next_review", ""),
            last_reviewed=data.get("last_reviewed"),
            review_count=data.get("review_count", 0),
            correct_streak=data.get("correct_streak", 0),
            times_correct=data.get("times_correct", 0),
            times_incorrect=data.get("times_incorrect", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class ReviewSession:
    """Active review session."""
    session_id: str
    cards_to_review: List[str]  # Card IDs
    current_index: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_complete(self) -> bool:
        return self.current_index >= len(self.cards_to_review)

    @property
    def progress(self) -> float:
        if not self.cards_to_review:
            return 1.0
        return self.current_index / len(self.cards_to_review)

    @property
    def total_cards(self) -> int:
        return len(self.cards_to_review)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "cards_to_review": self.cards_to_review,
            "current_index": self.current_index,
            "correct_count": self.correct_count,
            "incorrect_count": self.incorrect_count,
            "total_cards": self.total_cards,
            "progress": self.progress,
            "is_complete": self.is_complete,
            "started_at": self.started_at,
        }


class ReviewCardManager:
    """Manages the review card deck."""

    def __init__(self):
        self.cards: Dict[str, ReviewCard] = {}
        self.load()

    def load(self):
        """Load cards from file."""
        REVIEW_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

        if REVIEW_DATA_FILE.exists():
            try:
                with open(REVIEW_DATA_FILE, 'r') as f:
                    data = json.load(f)
                for card_data in data.get("cards", []):
                    card = ReviewCard.from_dict(card_data)
                    self.cards[card.card_id] = card
            except Exception as e:
                print(f"Error loading review cards: {e}")

    def save(self):
        """Save cards to file."""
        REVIEW_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"cards": [c.to_dict() for c in self.cards.values()]}
        with open(REVIEW_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def add_card(self, card: ReviewCard) -> str:
        """Add a new card and return its ID."""
        if not card.card_id:
            card.card_id = str(uuid.uuid4())[:8]

        # Set initial next_review to now (due immediately)
        card.next_review = datetime.now().isoformat()
        self.cards[card.card_id] = card
        self.save()
        return card.card_id

    def get_card(self, card_id: str) -> Optional[ReviewCard]:
        """Get a card by ID."""
        return self.cards.get(card_id)

    def get_due_cards(self, limit: int = 20, card_type: Optional[str] = None) -> List[ReviewCard]:
        """Get cards due for review, sorted by priority."""
        now = datetime.now()
        due = []

        for card in self.cards.values():
            # Filter by type if specified
            if card_type and card.card_type != card_type:
                continue

            # Check if due
            if card.is_due:
                due.append(card)

        # Sort: lower box (less mastered) first, then by next_review
        due.sort(key=lambda c: (c.box, c.next_review or ""))
        return due[:limit]

    def record_result(self, card_id: str, correct: bool) -> Optional[ReviewCard]:
        """Record review result and update Leitner box."""
        if card_id not in self.cards:
            return None

        card = self.cards[card_id]
        card.review_count += 1
        card.last_reviewed = datetime.now().isoformat()

        if correct:
            card.times_correct += 1
            card.correct_streak += 1
            # Move up a box (max 6)
            if card.box < 6:
                card.box += 1
        else:
            card.times_incorrect += 1
            card.correct_streak = 0
            # Move back to box 1
            card.box = 1

        # Calculate next review time
        interval_days = LEITNER_INTERVALS.get(card.box, 1)
        card.next_review = (datetime.now() + timedelta(days=interval_days)).isoformat()

        self.save()
        return card

    def get_stats(self) -> Dict[str, Any]:
        """Get overall review statistics."""
        total = len(self.cards)
        if total == 0:
            return {
                "total_cards": 0,
                "due_count": 0,
                "mastered_count": 0,
                "by_type": {},
                "average_box": 0,
            }

        due = len(self.get_due_cards(1000))
        mastered = sum(1 for c in self.cards.values() if c.box >= 5)

        by_type: Dict[str, int] = {}
        for card in self.cards.values():
            t = card.card_type
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_cards": total,
            "due_count": due,
            "mastered_count": mastered,
            "by_type": by_type,
            "average_box": sum(c.box for c in self.cards.values()) / total,
        }

    def create_opening_cards(self, opening_id: str, moves: List[tuple]) -> List[str]:
        """Create cards for an opening sequence.

        Args:
            opening_id: ID of the opening
            moves: List of (fen, move_san, explanation) tuples

        Returns:
            List of created card IDs
        """
        card_ids = []
        for i, (fen, move_san, explanation) in enumerate(moves):
            card_id = f"{opening_id}_{i}"

            # Skip if card already exists
            if card_id in self.cards:
                card_ids.append(card_id)
                continue

            card = ReviewCard(
                card_id=card_id,
                card_type=CardType.OPENING_SEQUENCE.value,
                fen=fen,
                expected_move=move_san,
                opening_id=opening_id,
                move_number=i + 1,
                explanation=explanation,
            )
            self.cards[card.card_id] = card
            card_ids.append(card.card_id)

        self.save()
        return card_ids

    def create_blunder_card(
        self,
        fen: str,
        best_move: str,
        source_game: Optional[str] = None,
        explanation: str = "",
        move_number: int = 0
    ) -> str:
        """Create a card from a blunder position."""
        card = ReviewCard(
            card_id=str(uuid.uuid4())[:8],
            card_type=CardType.BLUNDER_POSITION.value,
            fen=fen,
            expected_move=best_move,
            source_game=source_game,
            move_number=move_number,
            explanation=explanation or f"Best move was {best_move}",
        )
        return self.add_card(card)

    def create_tactical_card(
        self,
        fen: str,
        best_move: str,
        theme: str,
        explanation: str = ""
    ) -> str:
        """Create a card for a tactical pattern."""
        card = ReviewCard(
            card_id=str(uuid.uuid4())[:8],
            card_type=CardType.TACTICAL_PATTERN.value,
            fen=fen,
            expected_move=best_move,
            tactical_theme=theme,
            explanation=explanation or f"Find the {theme}!",
        )
        return self.add_card(card)

    def delete_card(self, card_id: str) -> bool:
        """Delete a card by ID."""
        if card_id in self.cards:
            del self.cards[card_id]
            self.save()
            return True
        return False

    def reset_card(self, card_id: str) -> bool:
        """Reset a card to box 1."""
        if card_id in self.cards:
            card = self.cards[card_id]
            card.box = 1
            card.correct_streak = 0
            card.next_review = datetime.now().isoformat()
            self.save()
            return True
        return False


# Global manager instance
_review_manager: Optional[ReviewCardManager] = None


def get_review_manager() -> ReviewCardManager:
    """Get the global review card manager instance."""
    global _review_manager
    if _review_manager is None:
        _review_manager = ReviewCardManager()
    return _review_manager


def generate_opening_review_cards(opening_id: str) -> List[str]:
    """Generate review cards for an opening based on its main line.

    This should be called when a user first starts training an opening
    to populate their review deck.
    """
    import chess
    from .openings import get_opening_by_id

    opening = get_opening_by_id(opening_id)
    if not opening:
        return []

    manager = get_review_manager()
    moves_data = []

    # Create a board and replay the opening to get FEN positions
    board = chess.Board()

    # For Black openings, we need to play White's first move first
    if opening.color.value == "black" and opening.response_to:
        first_move = opening.response_to  # e.g., "e4" or "d4"
        try:
            board.push_san(first_move)
        except ValueError:
            pass

    # Now collect each position where the player needs to move
    for move_info in opening.main_line:
        fen = board.fen()
        moves_data.append((fen, move_info.move_san, move_info.explanation))

        # Play the move
        try:
            board.push_san(move_info.move_san)
        except ValueError:
            break

        # Play opponent's response if available
        if move_info.common_responses:
            try:
                board.push_san(move_info.common_responses[0])
            except ValueError:
                pass

    return manager.create_opening_cards(opening_id, moves_data)
