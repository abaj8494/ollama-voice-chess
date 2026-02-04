"""
Chess engine integration using Stockfish.

Stockfish handles the actual chess play (tactics, strategy).
The LLM is used only for explaining moves and conversation.
"""

import chess
import chess.engine
import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple
import asyncio

logger = logging.getLogger(__name__)

# Default Stockfish paths by platform
STOCKFISH_PATHS = [
    "/usr/local/bin/stockfish",
    "/usr/bin/stockfish",
    "/opt/homebrew/bin/stockfish",  # macOS ARM
    shutil.which("stockfish"),  # System PATH
]


class ChessEngine:
    """
    Wrapper for Stockfish chess engine.

    Provides:
    - Move generation at configurable skill levels
    - Position evaluation
    - Best move analysis with explanation data
    """

    def __init__(self, skill_level: int = 10, depth: int = 15, time_limit: float = 1.0):
        """
        Initialize the chess engine.

        Args:
            skill_level: Stockfish skill level 0-20 (0=weakest, 20=strongest)
            depth: Search depth for analysis
            time_limit: Time limit per move in seconds
        """
        self.skill_level = skill_level
        self.depth = depth
        self.time_limit = time_limit
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.engine_path: Optional[str] = None

    def find_stockfish(self) -> Optional[str]:
        """Find Stockfish executable."""
        for path in STOCKFISH_PATHS:
            if path and Path(path).exists():
                return path
        return None

    def start(self) -> bool:
        """Start the Stockfish engine."""
        self.engine_path = self.find_stockfish()

        if not self.engine_path:
            logger.warning("Stockfish not found. Install with: brew install stockfish")
            return False

        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.engine.configure({"Skill Level": self.skill_level})
            logger.info(f"Stockfish started (skill={self.skill_level}, path={self.engine_path})")
            return True
        except Exception as e:
            logger.error(f"Failed to start Stockfish: {e}")
            return False

    def stop(self):
        """Stop the engine."""
        if self.engine:
            try:
                self.engine.quit()
            except:
                pass
            self.engine = None

    def is_running(self) -> bool:
        """Check if engine is running."""
        return self.engine is not None

    def _pv_to_san(self, board: chess.Board, pv: list, max_moves: int = 5) -> list:
        """
        Convert a principal variation (list of moves) to SAN notation.

        Uses a board copy to properly convert each move in sequence.
        """
        san_moves = []
        temp_board = board.copy()
        for move in pv[:max_moves]:
            try:
                san_moves.append(temp_board.san(move))
                temp_board.push(move)
            except Exception:
                break  # Stop if we hit an invalid move
        return san_moves

    def get_best_move(self, board: chess.Board) -> Optional[Tuple[chess.Move, dict]]:
        """
        Get the best move for the current position.

        Returns:
            Tuple of (move, analysis_info) or None if engine unavailable
        """
        if not self.engine:
            return None

        try:
            # Get analysis with info
            result = self.engine.analyse(
                board,
                chess.engine.Limit(time=self.time_limit, depth=self.depth)
            )

            move = result.get("pv", [None])[0]
            if not move:
                # Fallback to play
                result = self.engine.play(
                    board,
                    chess.engine.Limit(time=self.time_limit)
                )
                move = result.move

            # Extract analysis info
            pv = result.get("pv", [])
            info = {
                "move": board.san(move) if move else None,
                "score": self._format_score(result.get("score")),
                "depth": result.get("depth", 0),
                "pv": self._pv_to_san(board, pv),  # Principal variation
                "nodes": result.get("nodes", 0),
            }

            return move, info

        except Exception as e:
            logger.error(f"Engine error: {e}")
            return None

    def evaluate_position(self, board: chess.Board) -> dict:
        """
        Evaluate the current position.

        Returns dict with:
        - score: Evaluation in pawns (+ = white advantage)
        - best_moves: Top 3 moves with evaluations
        - is_tactical: Whether position has forcing moves
        """
        if not self.engine:
            return {"score": 0, "best_moves": [], "is_tactical": False}

        try:
            # Multi-PV analysis for top moves
            result = self.engine.analyse(
                board,
                chess.engine.Limit(time=self.time_limit),
                multipv=3
            )

            if isinstance(result, list):
                analyses = result
            else:
                analyses = [result]

            best_moves = []
            for analysis in analyses:
                pv = analysis.get("pv", [])
                if pv:
                    best_moves.append({
                        "move": board.san(pv[0]),
                        "score": self._format_score(analysis.get("score")),
                        "line": self._pv_to_san(board, pv, max_moves=4)
                    })

            main_score = analyses[0].get("score") if analyses else None

            return {
                "score": self._format_score(main_score),
                "best_moves": best_moves,
                "is_tactical": self._is_tactical(main_score),
            }

        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {"score": 0, "best_moves": [], "is_tactical": False}

    def _format_score(self, score) -> str:
        """Format engine score for display."""
        if score is None:
            return "0.0"

        pov_score = score.white()  # From white's perspective

        if pov_score.is_mate():
            mate_in = pov_score.mate()
            return f"M{mate_in}" if mate_in > 0 else f"M{mate_in}"
        else:
            cp = pov_score.score()
            if cp is not None:
                return f"{cp / 100:.1f}"
            return "0.0"

    def _is_tactical(self, score) -> bool:
        """Check if position is tactical (big eval swing possible)."""
        if score is None:
            return False
        pov = score.white()
        if pov.is_mate():
            return True
        cp = pov.score()
        return cp is not None and abs(cp) > 150  # > 1.5 pawns

    def set_skill_level(self, level: int):
        """Set engine skill level (0-20)."""
        self.skill_level = max(0, min(20, level))
        if self.engine:
            self.engine.configure({"Skill Level": self.skill_level})
        logger.info(f"Skill level set to {self.skill_level}")

    def get_move_explanation_context(self, board: chess.Board, move: chess.Move) -> str:
        """
        Generate context for LLM to explain a move.

        Returns a string describing what the move does tactically.
        """
        san = board.san(move)
        explanations = []

        # Check what the move does
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured:
                explanations.append(f"captures {chess.piece_name(captured.piece_type)}")

        # Check for checks
        board.push(move)
        if board.is_check():
            if board.is_checkmate():
                explanations.append("delivers checkmate")
            else:
                explanations.append("gives check")
        board.pop()

        # Check for castling
        if board.is_castling(move):
            if board.is_kingside_castling(move):
                explanations.append("castles kingside for safety")
            else:
                explanations.append("castles queenside")

        # Check for pawn moves
        piece = board.piece_at(move.from_square)
        if piece and piece.piece_type == chess.PAWN:
            if chess.square_rank(move.to_square) in [0, 7]:
                explanations.append("promotes")
            elif abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square)) == 2:
                explanations.append("advances two squares to control center")

        if explanations:
            return f"{san} - {', '.join(explanations)}"
        return san

    def generate_move_commentary(
        self,
        board: chess.Board,
        move: chess.Move,
        analysis: dict
    ) -> str:
        """
        Generate accurate, non-hallucinating commentary for a move.

        Based purely on board state and Stockfish analysis - no LLM guessing.
        """
        san = board.san(move)
        comments = []

        piece = board.piece_at(move.from_square)
        piece_name = chess.piece_name(piece.piece_type).capitalize() if piece else "Piece"
        is_white = piece.color == chess.WHITE if piece else True

        # What does the move physically do?
        if board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured:
                cap_name = chess.piece_name(captured.piece_type)
                comments.append(f"taking the {cap_name}")

        # Check for castling
        if board.is_castling(move):
            if board.is_kingside_castling(move):
                return f"{san}. Castling short for king safety."
            else:
                return f"{san}. Castling long."

        # Check for checks after the move
        board.push(move)
        is_check = board.is_check()
        is_checkmate = board.is_checkmate()
        board.pop()

        if is_checkmate:
            return f"{san}. Checkmate!"
        if is_check:
            comments.append("with check")

        # Pawn-specific comments
        if piece and piece.piece_type == chess.PAWN:
            to_rank = chess.square_rank(move.to_square)
            from_rank = chess.square_rank(move.from_square)

            if to_rank in [0, 7]:
                comments.append("promoting")
            elif abs(to_rank - from_rank) == 2:
                # Double pawn push
                to_file = chess.square_file(move.to_square)
                if to_file in [3, 4]:  # d or e file
                    comments.append("fighting for the center")
                else:
                    comments.append("pushing forward")

        # Development comments for minor pieces
        if piece and piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
            from_rank = chess.square_rank(move.from_square)
            start_rank = 0 if is_white else 7
            if from_rank == start_rank:
                comments.append("developing")

        # Use evaluation to add context
        score_str = analysis.get('score', '0.0')
        try:
            if score_str.startswith('M'):
                mate_in = int(score_str[1:])
                if (mate_in > 0) == (not is_white):  # AI is winning
                    comments.append(f"mate in {abs(mate_in)}")
            else:
                score = float(score_str)
                # From AI's perspective (playing as black usually)
                if not is_white:  # AI just moved as black
                    if score < -1.5:
                        comments.append("gaining advantage")
                    elif score < -3.0:
                        comments.append("winning position")
        except (ValueError, TypeError):
            pass

        # Build the final comment
        if comments:
            comment_str = ", ".join(comments)
            # Capitalize first letter
            comment_str = comment_str[0].upper() + comment_str[1:]
            return f"{san}. {comment_str}."
        else:
            # Generic but honest fallback based on piece type
            if piece:
                if piece.piece_type == chess.KNIGHT:
                    return f"{san}. Repositioning the knight."
                elif piece.piece_type == chess.BISHOP:
                    return f"{san}. Placing the bishop."
                elif piece.piece_type == chess.ROOK:
                    return f"{san}. Activating the rook."
                elif piece.piece_type == chess.QUEEN:
                    return f"{san}. Moving the queen."
                elif piece.piece_type == chess.KING:
                    return f"{san}. Moving the king."
                elif piece.piece_type == chess.PAWN:
                    return f"{san}. Advancing the pawn."
            return f"{san}."


# Global engine instance
_engine: Optional[ChessEngine] = None


def get_engine() -> ChessEngine:
    """Get or create the global engine instance."""
    global _engine
    if _engine is None:
        _engine = ChessEngine(skill_level=10)
        _engine.start()
    return _engine


def set_engine_skill(level: int):
    """Set the global engine skill level."""
    engine = get_engine()
    engine.set_skill_level(level)
