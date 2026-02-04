"""
Game analysis module for post-game review and blunder detection.

Uses Stockfish to evaluate positions and identify mistakes.
"""

import chess
import chess.pgn
import io
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from .engine import get_engine

logger = logging.getLogger(__name__)


@dataclass
class MoveAnalysis:
    """Analysis of a single move."""
    move_number: int
    color: str  # "white" or "black"
    move_san: str
    eval_before: float
    eval_after: float
    eval_change: float
    best_move: Optional[str]
    best_eval: Optional[float]
    classification: str  # "brilliant", "great", "best", "good", "book", "inaccuracy", "mistake", "blunder"
    comment: str
    is_capture: bool = False
    is_check: bool = False
    is_sacrifice: bool = False
    fen_after: str = ""  # FEN position after this move


@dataclass
class GameAnalysis:
    """Complete analysis of a game."""
    moves: List[MoveAnalysis]
    white_blunders: int
    white_mistakes: int
    white_inaccuracies: int
    black_blunders: int
    black_mistakes: int
    black_inaccuracies: int
    critical_moments: List[int]  # Move numbers of critical moments
    summary: str


# Thresholds for move classification (in centipawns)
BLUNDER_THRESHOLD = 200  # > 2 pawns lost
MISTAKE_THRESHOLD = 100  # > 1 pawn lost
INACCURACY_THRESHOLD = 50  # > 0.5 pawns lost


def classify_move(
    eval_change: float,
    had_better_move: bool,
    is_sacrifice: bool = False,
    eval_before: float = 0,
    eval_after: float = 0,
    is_only_good_move: bool = False
) -> str:
    """
    Classify a move based on evaluation change and context.

    Classifications (best to worst):
    - brilliant: Sacrifice that improves position significantly or only winning move in critical position
    - great: Finds a very strong move that significantly improves position (+1 pawn or more)
    - best: The engine's top choice
    - good: Close to best, small loss (<0.1 pawns)
    - book: Standard opening move (handled separately)
    - inaccuracy: Small mistake (0.5-1 pawn loss)
    - mistake: Moderate mistake (1-2 pawns loss)
    - blunder: Serious mistake (>2 pawns loss)
    """
    # eval_change is from the moving side's perspective (negative = bad)

    # Brilliant: Sacrifice that works, or only winning move in critical position
    if is_sacrifice and eval_change >= 50:  # Sacrifice that gains advantage
        return "brilliant"

    if is_only_good_move and eval_before < -100 and eval_after > 0:
        # Found the only move to save a losing position
        return "brilliant"

    # Great: Significant improvement (gaining 1+ pawns worth)
    if eval_change >= 100 and not had_better_move:
        return "great"

    # Best: Engine's top choice with minimal or no loss
    if eval_change >= -10:
        return "best" if not had_better_move else "good"

    # Good: Close to best
    elif eval_change >= -INACCURACY_THRESHOLD:
        return "good"

    # Errors
    elif eval_change >= -MISTAKE_THRESHOLD:
        return "inaccuracy"
    elif eval_change >= -BLUNDER_THRESHOLD:
        return "mistake"
    else:
        return "blunder"


def get_classification_comment(classification: str, eval_change: float, best_move: Optional[str], is_sacrifice: bool = False) -> str:
    """Generate a comment for a move classification."""
    if classification == "brilliant":
        if is_sacrifice:
            return "Brilliant sacrifice!"
        return "Brilliant! The only winning move."
    elif classification == "great":
        return f"Great move! Gains {eval_change/100:.1f} pawns."
    elif classification == "best":
        return "Best move."
    elif classification == "good":
        return "Good move."
    elif classification == "book":
        return "Book move."
    elif classification == "inaccuracy":
        if best_move:
            return f"Inaccuracy. {best_move} was better."
        return "Slight inaccuracy."
    elif classification == "mistake":
        if best_move:
            return f"Mistake! {best_move} was much better ({abs(eval_change)/100:.1f} pawns lost)."
        return f"Mistake! ({abs(eval_change)/100:.1f} pawns lost)"
    elif classification == "blunder":
        if best_move:
            return f"Blunder! {best_move} was winning. ({abs(eval_change)/100:.1f} pawns lost)"
        return f"Blunder! ({abs(eval_change)/100:.1f} pawns lost)"
    return ""


def analyze_game(pgn_text: str, depth: int = 12) -> Optional[GameAnalysis]:
    """
    Analyze a complete game from PGN.

    Args:
        pgn_text: PGN string of the game
        depth: Analysis depth for Stockfish

    Returns:
        GameAnalysis object with full breakdown
    """
    engine = get_engine()
    if not engine.is_running():
        logger.error("Stockfish not available for analysis")
        return None

    try:
        pgn_io = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_io)
        if not game:
            return None

        board = game.board()
        moves_analysis = []

        white_blunders = 0
        white_mistakes = 0
        white_inaccuracies = 0
        black_blunders = 0
        black_mistakes = 0
        black_inaccuracies = 0
        critical_moments = []

        move_number = 1
        prev_eval = 0.0  # Start from equal position

        for node in game.mainline():
            move = node.move
            is_white = board.turn == chess.WHITE

            # Get evaluation before the move
            eval_before = prev_eval

            # Detect move properties BEFORE making the move
            is_capture = board.is_capture(move)
            is_check = board.gives_check(move)

            # Detect sacrifice: giving up material for position
            is_sacrifice = False
            if is_capture:
                # Check if we're capturing with a more valuable piece
                moving_piece = board.piece_at(move.from_square)
                captured_piece = board.piece_at(move.to_square)
                if moving_piece and captured_piece:
                    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                                   chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
                    if piece_values.get(moving_piece.piece_type, 0) > piece_values.get(captured_piece.piece_type, 0):
                        is_sacrifice = True  # Potentially a sacrifice

            # Get best move for this position
            result = engine.get_best_move(board)
            best_move_san = None
            best_eval = None
            if result:
                best_move, analysis = result
                best_move_san = analysis['move']
                best_eval = parse_eval(analysis['score'])
                if not is_white:
                    best_eval = -best_eval  # Normalize to white's perspective

            # Make the move
            move_san = board.san(move)
            board.push(move)

            # Store FEN after move for replay
            fen_after = board.fen()

            # Get evaluation after the move
            result_after = engine.get_best_move(board)
            if result_after:
                _, analysis_after = result_after
                eval_after = parse_eval(analysis_after['score'])
            else:
                eval_after = prev_eval

            # Calculate eval change from moving side's perspective
            if is_white:
                eval_change = eval_after - eval_before
            else:
                eval_change = -eval_after - (-eval_before)  # From black's perspective

            # Check if there was a better move
            played_is_best = best_move_san and move_san == best_move_san
            had_better_move = best_eval is not None and not played_is_best

            # Check if this was the only good move (for brilliant detection)
            is_only_good_move = played_is_best and eval_before < -100 and eval_after > -50

            # Classify the move with full context
            classification = classify_move(
                eval_change=eval_change,
                had_better_move=had_better_move,
                is_sacrifice=is_sacrifice,
                eval_before=eval_before,
                eval_after=eval_after,
                is_only_good_move=is_only_good_move
            )
            comment = get_classification_comment(
                classification, eval_change,
                best_move_san if had_better_move else None,
                is_sacrifice=is_sacrifice
            )

            # Track statistics
            if is_white:
                if classification == "blunder":
                    white_blunders += 1
                elif classification == "mistake":
                    white_mistakes += 1
                elif classification == "inaccuracy":
                    white_inaccuracies += 1
            else:
                if classification == "blunder":
                    black_blunders += 1
                elif classification == "mistake":
                    black_mistakes += 1
                elif classification == "inaccuracy":
                    black_inaccuracies += 1

            # Track critical moments (both errors and brilliant moves)
            if classification in ["blunder", "mistake", "brilliant", "great"]:
                critical_moments.append(move_number if is_white else move_number)

            moves_analysis.append(MoveAnalysis(
                move_number=move_number,
                color="white" if is_white else "black",
                move_san=move_san,
                eval_before=eval_before,
                eval_after=eval_after,
                eval_change=eval_change,
                best_move=best_move_san if had_better_move else None,
                best_eval=best_eval,
                classification=classification,
                comment=comment,
                is_capture=is_capture,
                is_check=is_check,
                is_sacrifice=is_sacrifice,
                fen_after=fen_after,
            ))

            # Update for next iteration
            prev_eval = eval_after
            if not is_white:
                move_number += 1

        # Generate summary
        summary = generate_game_summary(
            moves_analysis, white_blunders, white_mistakes, white_inaccuracies,
            black_blunders, black_mistakes, black_inaccuracies
        )

        return GameAnalysis(
            moves=moves_analysis,
            white_blunders=white_blunders,
            white_mistakes=white_mistakes,
            white_inaccuracies=white_inaccuracies,
            black_blunders=black_blunders,
            black_mistakes=black_mistakes,
            black_inaccuracies=black_inaccuracies,
            critical_moments=critical_moments,
            summary=summary,
        )

    except Exception as e:
        logger.error(f"Game analysis error: {e}")
        return None


def parse_eval(score_str: str) -> float:
    """Parse evaluation string to float."""
    try:
        if score_str.startswith('M'):
            # Mate score - use large value
            mate_in = int(score_str[1:])
            return 1000 if mate_in > 0 else -1000
        return float(score_str)
    except (ValueError, TypeError):
        return 0.0


def generate_game_summary(
    moves: List[MoveAnalysis],
    white_blunders: int, white_mistakes: int, white_inaccuracies: int,
    black_blunders: int, black_mistakes: int, black_inaccuracies: int
) -> str:
    """Generate a text summary of the game analysis."""
    lines = []

    lines.append("Game Analysis Summary")
    lines.append("=" * 40)
    lines.append("")

    lines.append("White:")
    lines.append(f"  Blunders: {white_blunders}")
    lines.append(f"  Mistakes: {white_mistakes}")
    lines.append(f"  Inaccuracies: {white_inaccuracies}")
    lines.append("")

    lines.append("Black:")
    lines.append(f"  Blunders: {black_blunders}")
    lines.append(f"  Mistakes: {black_mistakes}")
    lines.append(f"  Inaccuracies: {black_inaccuracies}")
    lines.append("")

    # Find critical moments
    critical = [m for m in moves if m.classification in ["blunder", "mistake"]]
    if critical:
        lines.append("Critical moments:")
        for m in critical[:5]:
            lines.append(f"  Move {m.move_number}. {m.move_san} ({m.color}): {m.comment}")

    return "\n".join(lines)


def check_blunder(board_before: chess.Board, move: chess.Move, threshold: float = MISTAKE_THRESHOLD) -> Tuple[bool, Optional[str], float]:
    """
    Quick check if a move is a blunder.

    Args:
        board_before: Position before the move
        move: The move to check
        threshold: Centipawn threshold for blunder detection

    Returns:
        Tuple of (is_blunder, best_move, eval_loss)
    """
    engine = get_engine()
    if not engine.is_running():
        return False, None, 0.0

    # Get eval and best move before
    result_before = engine.get_best_move(board_before)
    if not result_before:
        return False, None, 0.0

    best_move, analysis_before = result_before
    eval_before = parse_eval(analysis_before['score'])
    best_move_san = analysis_before['move']

    # Make the move
    board_after = board_before.copy()
    board_after.push(move)

    # Get eval after
    result_after = engine.get_best_move(board_after)
    if not result_after:
        return False, None, 0.0

    _, analysis_after = result_after
    eval_after = parse_eval(analysis_after['score'])

    # Calculate loss from moving side's perspective
    is_white = board_before.turn == chess.WHITE
    if is_white:
        eval_loss = (eval_before - eval_after) * 100  # Convert to centipawns
    else:
        eval_loss = ((-eval_before) - (-eval_after)) * 100

    # Check if it's a blunder
    is_blunder = eval_loss > threshold
    played_san = board_before.san(move)

    return is_blunder, best_move_san if is_blunder and played_san != best_move_san else None, eval_loss


def get_position_assessment(board: chess.Board) -> Dict:
    """
    Get a quick assessment of the current position.

    Returns dict with evaluation, best moves, and key features.
    """
    engine = get_engine()
    if not engine.is_running():
        return {"error": "Engine not available"}

    eval_result = engine.evaluate_position(board)

    return {
        "evaluation": eval_result.get('score', '0.0'),
        "best_moves": eval_result.get('best_moves', []),
        "is_tactical": eval_result.get('is_tactical', False),
        "material": get_material_balance(board),
    }


def get_material_balance(board: chess.Board) -> Dict:
    """Calculate material balance."""
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
    }

    white_material = 0
    black_material = 0

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece and piece.piece_type != chess.KING:
            value = piece_values.get(piece.piece_type, 0)
            if piece.color == chess.WHITE:
                white_material += value
            else:
                black_material += value

    return {
        "white": white_material,
        "black": black_material,
        "balance": white_material - black_material,
        "description": get_material_description(white_material - black_material),
    }


def get_material_description(balance: int) -> str:
    """Get human-readable material balance description."""
    if balance == 0:
        return "Material is equal"
    elif balance > 0:
        if balance >= 9:
            return f"White is up a queen ({balance} points)"
        elif balance >= 5:
            return f"White is up a rook ({balance} points)"
        elif balance >= 3:
            return f"White is up a minor piece ({balance} points)"
        else:
            return f"White is up {balance} pawn(s)"
    else:
        balance = abs(balance)
        if balance >= 9:
            return f"Black is up a queen ({balance} points)"
        elif balance >= 5:
            return f"Black is up a rook ({balance} points)"
        elif balance >= 3:
            return f"Black is up a minor piece ({balance} points)"
        else:
            return f"Black is up {balance} pawn(s)"
