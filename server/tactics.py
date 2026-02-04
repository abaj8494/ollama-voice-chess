"""
Tactical pattern detection for chess positions.

Identifies pins, forks, skewers, discovered attacks, and other tactical motifs.
All detection is done programmatically - no LLM guessing.
"""

import chess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TacticalMotif:
    """Represents a detected tactical pattern."""
    type: str  # "pin", "fork", "skewer", "discovered_attack", "hanging_piece"
    attacker_square: Optional[int]
    target_squares: List[int]
    description: str
    severity: str  # "info", "warning", "critical"


def analyze_tactics(board: chess.Board) -> List[TacticalMotif]:
    """
    Analyze the current position for tactical motifs.

    Returns a list of detected tactical patterns.
    """
    motifs = []

    motifs.extend(find_pins(board))
    motifs.extend(find_forks(board))
    motifs.extend(find_hanging_pieces(board))
    motifs.extend(find_skewers(board))

    return motifs


def find_pins(board: chess.Board) -> List[TacticalMotif]:
    """Find all pins in the position."""
    motifs = []

    for color in [chess.WHITE, chess.BLACK]:
        # Check pins against the king
        king_square = board.king(color)
        if king_square is None:
            continue

        # Find pieces that could be pinned
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None or piece.color != color:
                continue
            if square == king_square:
                continue

            # Check if this piece is between an attacker and the king
            pin_attacker = get_pinner(board, square, king_square, not color)
            if pin_attacker is not None:
                pinned_piece = board.piece_at(square)
                attacker_piece = board.piece_at(pin_attacker)

                motifs.append(TacticalMotif(
                    type="pin",
                    attacker_square=pin_attacker,
                    target_squares=[square, king_square],
                    description=f"{chess.piece_name(pinned_piece.piece_type).capitalize()} on {chess.square_name(square)} is pinned to the king by {chess.piece_name(attacker_piece.piece_type)}",
                    severity="warning" if pinned_piece.piece_type in [chess.QUEEN, chess.ROOK] else "info"
                ))

    return motifs


def get_pinner(board: chess.Board, pinned_square: int, king_square: int, attacker_color: bool) -> Optional[int]:
    """Check if a piece is pinned and return the pinner's square."""
    # Get the ray from king through the potentially pinned piece
    if not is_on_same_line(pinned_square, king_square):
        return None

    # Direction from king to pinned piece
    direction = get_direction(king_square, pinned_square)
    if direction is None:
        return None

    # Look for attacker beyond the pinned piece
    current = pinned_square
    while True:
        current = current + direction
        if current < 0 or current > 63:
            break
        # Check if we went off the board (file wrap)
        if abs((current % 8) - ((current - direction) % 8)) > 1:
            break

        piece = board.piece_at(current)
        if piece is None:
            continue

        if piece.color != attacker_color:
            break  # Blocked by friendly piece

        # Check if this piece can attack along this line
        if can_attack_along_line(piece.piece_type, direction):
            return current
        else:
            break

    return None


def is_on_same_line(sq1: int, sq2: int) -> bool:
    """Check if two squares are on the same rank, file, or diagonal."""
    r1, f1 = sq1 // 8, sq1 % 8
    r2, f2 = sq2 // 8, sq2 % 8

    return r1 == r2 or f1 == f2 or abs(r1 - r2) == abs(f1 - f2)


def get_direction(from_sq: int, to_sq: int) -> Optional[int]:
    """Get the direction delta from one square to another."""
    r1, f1 = from_sq // 8, from_sq % 8
    r2, f2 = to_sq // 8, to_sq % 8

    dr = 0 if r2 == r1 else (1 if r2 > r1 else -1)
    df = 0 if f2 == f1 else (1 if f2 > f1 else -1)

    return dr * 8 + df


def can_attack_along_line(piece_type: int, direction: int) -> bool:
    """Check if a piece type can attack along a given direction."""
    is_diagonal = direction in [-9, -7, 7, 9]
    is_straight = direction in [-8, -1, 1, 8]

    if piece_type == chess.QUEEN:
        return True
    elif piece_type == chess.ROOK:
        return is_straight
    elif piece_type == chess.BISHOP:
        return is_diagonal
    return False


def find_forks(board: chess.Board) -> List[TacticalMotif]:
    """Find fork opportunities (one piece attacking multiple valuable pieces)."""
    motifs = []

    for color in [chess.WHITE, chess.BLACK]:
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None or piece.color != color:
                continue

            # Get all squares this piece attacks
            attacks = list(board.attacks(square))
            valuable_targets = []

            for target_sq in attacks:
                target = board.piece_at(target_sq)
                if target and target.color != color:
                    # Valuable pieces: Queen, Rook, or King
                    if target.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                        valuable_targets.append((target_sq, target))
                    # Knight/Bishop fork is also notable
                    elif target.piece_type in [chess.KNIGHT, chess.BISHOP] and piece.piece_type == chess.PAWN:
                        valuable_targets.append((target_sq, target))

            if len(valuable_targets) >= 2:
                target_names = [f"{chess.piece_name(t[1].piece_type)} on {chess.square_name(t[0])}"
                               for t in valuable_targets[:3]]
                motifs.append(TacticalMotif(
                    type="fork",
                    attacker_square=square,
                    target_squares=[t[0] for t in valuable_targets],
                    description=f"{chess.piece_name(piece.piece_type).capitalize()} on {chess.square_name(square)} forks {' and '.join(target_names)}",
                    severity="critical" if chess.KING in [t[1].piece_type for t in valuable_targets] else "warning"
                ))

    return motifs


def find_hanging_pieces(board: chess.Board) -> List[TacticalMotif]:
    """Find undefended pieces that are attacked."""
    motifs = []

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        if piece.piece_type == chess.PAWN:
            continue  # Skip pawns for now

        color = piece.color
        attackers = board.attackers(not color, square)
        defenders = board.attackers(color, square)

        if attackers and not defenders:
            attacker_squares = list(attackers)
            motifs.append(TacticalMotif(
                type="hanging_piece",
                attacker_square=attacker_squares[0] if attacker_squares else None,
                target_squares=[square],
                description=f"{'White' if color else 'Black'} {chess.piece_name(piece.piece_type)} on {chess.square_name(square)} is undefended and attacked",
                severity="critical" if piece.piece_type in [chess.QUEEN, chess.ROOK] else "warning"
            ))

    return motifs


def find_skewers(board: chess.Board) -> List[TacticalMotif]:
    """Find skewers (valuable piece attacked, less valuable piece behind it)."""
    motifs = []

    for color in [chess.WHITE, chess.BLACK]:
        # Look at all sliding pieces
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is None or piece.color != color:
                continue
            if piece.piece_type not in [chess.QUEEN, chess.ROOK, chess.BISHOP]:
                continue

            # Check all directions this piece can attack
            directions = []
            if piece.piece_type in [chess.QUEEN, chess.ROOK]:
                directions.extend([-8, 8, -1, 1])  # Straight
            if piece.piece_type in [chess.QUEEN, chess.BISHOP]:
                directions.extend([-9, -7, 7, 9])  # Diagonal

            for direction in directions:
                skewer = check_skewer_direction(board, square, direction, color)
                if skewer:
                    front_piece, back_piece, front_sq, back_sq = skewer
                    motifs.append(TacticalMotif(
                        type="skewer",
                        attacker_square=square,
                        target_squares=[front_sq, back_sq],
                        description=f"{chess.piece_name(piece.piece_type).capitalize()} skewers {chess.piece_name(front_piece.piece_type)} to {chess.piece_name(back_piece.piece_type)}",
                        severity="warning"
                    ))

    return motifs


def check_skewer_direction(board: chess.Board, attacker_sq: int, direction: int, attacker_color: bool) -> Optional[Tuple]:
    """Check if there's a skewer along a direction."""
    current = attacker_sq + direction
    first_piece = None
    first_sq = None

    while 0 <= current <= 63:
        # Check for file wrap
        if abs((current % 8) - ((current - direction) % 8)) > 1:
            break

        piece = board.piece_at(current)
        if piece:
            if piece.color == attacker_color:
                break  # Own piece blocks

            if first_piece is None:
                first_piece = piece
                first_sq = current
            else:
                # Found second piece - check if it's a skewer
                # Skewer: front piece is more valuable than back piece
                piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                               chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
                if piece_values.get(first_piece.piece_type, 0) > piece_values.get(piece.piece_type, 0):
                    return (first_piece, piece, first_sq, current)
                break

        current += direction

    return None


def analyze_move_tactics(board: chess.Board, move: chess.Move) -> Dict:
    """
    Analyze a move for tactical significance.

    Returns dict with:
    - creates_threat: bool
    - threats: list of threats created
    - tactical_motifs: list of motifs in the new position
    """
    # Analyze position before move
    before_tactics = analyze_tactics(board)

    # Make the move
    board.push(move)

    # Analyze position after move
    after_tactics = analyze_tactics(board)

    # Check for new threats
    new_threats = []
    for motif in after_tactics:
        # Check if this is a new threat (not present before)
        is_new = not any(
            m.type == motif.type and m.target_squares == motif.target_squares
            for m in before_tactics
        )
        if is_new:
            new_threats.append(motif)

    board.pop()

    return {
        "creates_threat": len(new_threats) > 0,
        "threats": new_threats,
        "tactical_motifs": after_tactics,
    }


def get_tactical_summary(board: chess.Board) -> str:
    """Get a human-readable summary of tactical features in the position."""
    motifs = analyze_tactics(board)

    if not motifs:
        return "No immediate tactical threats detected."

    lines = []
    critical = [m for m in motifs if m.severity == "critical"]
    warnings = [m for m in motifs if m.severity == "warning"]

    if critical:
        lines.append("Critical threats:")
        for m in critical[:3]:
            lines.append(f"  - {m.description}")

    if warnings:
        lines.append("Tactical features:")
        for m in warnings[:3]:
            lines.append(f"  - {m.description}")

    return "\n".join(lines)
