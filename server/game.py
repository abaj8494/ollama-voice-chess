"""
Chess game logic with full move validation using python-chess.
"""

import chess
import chess.pgn
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import io


@dataclass
class GameState:
    """Represents the current state of a chess game."""
    board: chess.Board = field(default_factory=chess.Board)
    player_color: str = "white"  # "white" or "black"
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert game state to a dictionary for JSON serialization."""
        history = self.board.move_stack
        move_list = []
        temp_board = chess.Board()

        for move in history:
            san = temp_board.san(move)
            move_list.append(san)
            temp_board.push(move)

        return {
            "fen": self.board.fen(),
            "player_color": self.player_color,
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "move_count": len(history),
            "half_moves": len(history),
            "full_moves": (len(history) + 1) // 2,
            "moves": move_list,
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "is_game_over": self.board.is_game_over(),
            "legal_moves": [m.uci() for m in self.board.legal_moves],  # UCI for click-to-move
            "legal_moves_san": [self.board.san(m) for m in self.board.legal_moves],
            "result": self.get_result(),
        }

    def get_result(self) -> Optional[str]:
        """Get game result if game is over."""
        if self.board.is_checkmate():
            return "0-1" if self.board.turn == chess.WHITE else "1-0"
        elif self.board.is_stalemate() or self.board.is_insufficient_material():
            return "1/2-1/2"
        elif self.board.can_claim_draw():
            return "1/2-1/2"
        return None


class ChessGame:
    """
    Manages a chess game with full move validation and state tracking.
    """

    def __init__(self):
        self.state = GameState()

    def new_game(self, player_color: str = "white") -> Dict[str, Any]:
        """Start a new game."""
        self.state = GameState(player_color=player_color)
        return self.state.to_dict()

    def make_move(self, move_str: str) -> Dict[str, Any]:
        """
        Attempt to make a move. Accepts various formats:
        - SAN: e4, Nf3, O-O, Qxd7+
        - UCI: e2e4, g1f3

        Returns dict with success status and game state.
        """
        move = self._parse_move(move_str)

        if move is None:
            return {
                "success": False,
                "error": f"Invalid move: '{move_str}'. Legal moves: {', '.join(self.get_legal_moves()[:10])}...",
                "state": self.state.to_dict()
            }

        # Get SAN before pushing (for recording)
        san = self.state.board.san(move)
        self.state.board.push(move)

        return {
            "success": True,
            "move": san,
            "state": self.state.to_dict()
        }

    def _parse_move(self, move_str: str) -> Optional[chess.Move]:
        """Parse a move string in various formats."""
        move_str = move_str.strip()

        # Handle castling variations
        castling_map = {
            "0-0": "O-O",
            "0-0-0": "O-O-O",
            "o-o": "O-O",
            "o-o-o": "O-O-O",
        }
        move_str = castling_map.get(move_str.lower(), move_str)

        # Try SAN notation first
        try:
            return self.state.board.parse_san(move_str)
        except (chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError):
            pass

        # Try UCI notation
        try:
            return self.state.board.parse_uci(move_str.lower())
        except (chess.InvalidMoveError, chess.IllegalMoveError):
            pass

        return None

    def undo_move(self, count: int = 1) -> Dict[str, Any]:
        """Undo the last n moves."""
        undone = []
        for _ in range(count):
            if self.state.board.move_stack:
                move = self.state.board.pop()
                undone.append(str(move))
            else:
                break

        return {
            "success": len(undone) > 0,
            "undone_moves": undone,
            "state": self.state.to_dict()
        }

    def undo_last_pair(self) -> Dict[str, Any]:
        """Undo the last move pair (both player and AI moves)."""
        return self.undo_move(2)

    def get_legal_moves(self) -> List[str]:
        """Get list of legal moves in SAN notation."""
        return [self.state.board.san(m) for m in self.state.board.legal_moves]

    def get_fen(self) -> str:
        """Get FEN representation of current position."""
        return self.state.board.fen()

    def get_pgn(self) -> str:
        """Generate PGN for the game."""
        game = chess.pgn.Game()
        game.headers["Event"] = "Voice Chess vs Ollama"
        game.headers["Date"] = self.state.created_at.strftime("%Y.%m.%d")
        game.headers["White"] = "Human" if self.state.player_color == "white" else "Ollama"
        game.headers["Black"] = "Ollama" if self.state.player_color == "white" else "Human"

        result = self.state.get_result()
        if result:
            game.headers["Result"] = result

        # Replay moves to build game tree
        node = game
        temp_board = chess.Board()
        for move in self.state.board.move_stack:
            node = node.add_variation(move)
            temp_board.push(move)

        return str(game)

    def get_move_history(self) -> List[str]:
        """Get list of moves in SAN notation."""
        moves = []
        temp_board = chess.Board()
        for move in self.state.board.move_stack:
            moves.append(temp_board.san(move))
            temp_board.push(move)
        return moves

    def get_formatted_history(self) -> str:
        """Get move history in standard PGN-style format."""
        moves = self.get_move_history()
        if not moves:
            return "No moves yet."

        formatted = ""
        for i, move in enumerate(moves):
            if i % 2 == 0:
                formatted += f"{i // 2 + 1}. "
            formatted += f"{move} "

        return formatted.strip()

    def get_position_description(self) -> str:
        """Get a human-readable description of the position."""
        state = self.state.to_dict()

        desc = f"Position after {state['half_moves']} half-moves ({state['full_moves']} full moves).\n"
        desc += f"It's {'White' if state['turn'] == 'white' else 'Black'}'s turn.\n"

        if state['is_checkmate']:
            winner = "Black" if state['turn'] == 'white' else "White"
            desc += f"CHECKMATE! {winner} wins!\n"
        elif state['is_check']:
            desc += "The king is in CHECK!\n"
        elif state['is_stalemate']:
            desc += "STALEMATE! The game is drawn.\n"
        elif state['is_game_over']:
            desc += "The game is over (draw).\n"

        return desc

    def is_ai_turn(self) -> bool:
        """Check if it's the AI's turn."""
        current_turn = "white" if self.state.board.turn == chess.WHITE else "black"
        return current_turn != self.state.player_color

    def add_conversation(self, role: str, content: str):
        """Add a message to conversation history."""
        self.state.conversation_history.append({
            "role": role,
            "content": content
        })

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get conversation history for AI context."""
        return self.state.conversation_history
