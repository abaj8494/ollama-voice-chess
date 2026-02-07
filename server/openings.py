"""
Opening library for chess training.
Contains definitions for 5 openings to learn:
- As White: London System, Queen's Gambit
- As Black vs 1.e4: Caro-Kann, Scandinavian Defense
- As Black vs 1.d4: King's Indian Defense
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class OpeningColor(Enum):
    WHITE = "white"
    BLACK = "black"


@dataclass
class OpeningMove:
    """A single move in an opening sequence."""
    move_san: str           # e.g., "d4", "Bf4"
    explanation: str        # Why this move is played
    common_responses: List[str] = field(default_factory=list)  # Expected opponent moves


@dataclass
class Opening:
    """Complete opening definition."""
    id: str                 # e.g., "london_system"
    name: str               # e.g., "London System"
    color: OpeningColor     # Which color plays this opening
    description: str        # Brief description
    response_to: Optional[str] = None  # For Black openings: "e4" or "d4"
    main_line: List[OpeningMove] = field(default_factory=list)
    typical_plans: List[str] = field(default_factory=list)
    key_squares: List[str] = field(default_factory=list)


# Opening Library - hardcoded for reliability
OPENINGS: Dict[str, Opening] = {
    "london_system": Opening(
        id="london_system",
        name="London System",
        color=OpeningColor.WHITE,
        description="A solid, universal opening system for White. Develop the dark-squared bishop to f4 before playing e3.",
        main_line=[
            OpeningMove(
                "d4",
                "Control the center with your d-pawn. This is the foundation of the London System.",
                ["d5", "Nf6", "e6"]
            ),
            OpeningMove(
                "Bf4",
                "The key move! Develop your bishop BEFORE playing e3. This bishop belongs on f4.",
                ["Nf6", "c5", "e6", "d5"]
            ),
            OpeningMove(
                "e3",
                "Support d4 and prepare to develop your light-squared bishop to d3.",
                ["c5", "e6", "Nc6", "Nf6"]
            ),
            OpeningMove(
                "Nf3",
                "Develop your knight to its natural square, controlling e5.",
                ["Be7", "Bd6", "Nc6", "c5"]
            ),
            OpeningMove(
                "c3",
                "Support d4 firmly and prepare Nbd2. Your center is now rock solid.",
                ["O-O", "Nc6", "Qb6"]
            ),
            OpeningMove(
                "Bd3",
                "Develop your bishop to the a2-g8 diagonal. It eyes the kingside.",
                ["b6", "Nbd7", "Qc7"]
            ),
            OpeningMove(
                "Nbd2",
                "Complete your development. The knight can go to e5 or support e4 later.",
                ["O-O", "Be7"]
            ),
            OpeningMove(
                "O-O",
                "Castle for king safety. Your setup is complete - time to start your plans!",
                []
            ),
        ],
        typical_plans=[
            "Push for e4 when possible to gain space",
            "Maneuver knight to e5 - a powerful outpost",
            "Attack on the kingside with pieces",
            "If they play c5, you can take or hold with c3",
        ],
        key_squares=["f4", "d3", "e5", "c3"]
    ),

    "queens_gambit": Opening(
        id="queens_gambit",
        name="Queen's Gambit",
        color=OpeningColor.WHITE,
        description="Classical opening offering the c4 pawn for central control. Not a real gambit - you can win the pawn back!",
        main_line=[
            OpeningMove(
                "d4",
                "Control the center. The Queen's Gambit starts with d4.",
                ["d5", "Nf6"]
            ),
            OpeningMove(
                "c4",
                "The Queen's Gambit! Attack Black's d5 pawn. If they take, you get the center.",
                ["e6", "c6", "dxc4"]
            ),
            OpeningMove(
                "Nc3",
                "Develop with tempo, adding pressure to d5. Your knight controls key central squares.",
                ["Nf6", "Be7", "e6"]
            ),
            OpeningMove(
                "Nf3",
                "Natural development. Control e5 and prepare to castle.",
                ["Be7", "Nf6", "c6"]
            ),
            OpeningMove(
                "Bg5",
                "Pin the knight to the queen! This adds more pressure on d5.",
                ["O-O", "h6", "Be7"]
            ),
            OpeningMove(
                "e3",
                "Prepare Bd3. Solid and flexible - supports d4 and opens the bishop.",
                ["O-O", "Nbd7", "h6"]
            ),
            OpeningMove(
                "Bd3",
                "Develop on the a2-g8 diagonal. Eyes both the center and kingside.",
                ["Nbd7", "c6", "dxc4"]
            ),
            OpeningMove(
                "O-O",
                "Castle for safety. You have a great position with pressure on Black's center.",
                []
            ),
        ],
        typical_plans=[
            "Minority attack: push a4-a5-b4 to create weaknesses",
            "Central breakthrough with e4 when possible",
            "If they take c4, recapture with Bxc4 and you have the center",
            "Build pressure on the d-file after Rd1",
        ],
        key_squares=["c4", "d5", "e4", "g5"]
    ),

    "caro_kann": Opening(
        id="caro_kann",
        name="Caro-Kann Defense",
        color=OpeningColor.BLACK,
        response_to="e4",
        description="A solid defense where you support d5 with your c-pawn. Very reliable and leads to good endgames.",
        main_line=[
            OpeningMove(
                "c6",
                "Prepare to play d5 next move. Unlike e6, this keeps your light bishop free!",
                ["d4", "Nc3", "Nf3"]
            ),
            OpeningMove(
                "d5",
                "Challenge White's e4 pawn directly. This is the key idea of the Caro-Kann.",
                ["exd5", "e5", "Nc3"]
            ),
            OpeningMove(
                "dxe4",
                "Capture the pawn. This is the main line - you'll develop your bishop actively.",
                ["Nxe4"]
            ),
            OpeningMove(
                "Bf5",
                "The star move! Develop your bishop BEFORE playing e6. It's very active here.",
                ["Ng3", "Nc5", "Nf3"]
            ),
            OpeningMove(
                "Bg6",
                "Retreat the bishop to safety. It's still active on this diagonal.",
                ["h4", "Nf3", "Bc4"]
            ),
            OpeningMove(
                "h6",
                "Give your bishop an escape square on h7 if White plays h5.",
                ["Nf3", "h5", "Bc4"]
            ),
            OpeningMove(
                "Nd7",
                "Develop your knight. It can go to f6 or support e5 later.",
                ["Bd3", "Bc4", "Qe2"]
            ),
            OpeningMove(
                "Ngf6",
                "Complete your development. You have a solid position with active pieces!",
                ["O-O", "Bd3", "Qe2"]
            ),
        ],
        typical_plans=[
            "Your pawn structure is very solid with few weaknesses",
            "Aim for e6 and c5 to challenge White's center later",
            "You often get good endgames because of your solid pawns",
            "Keep your light bishop active - that's your advantage!",
        ],
        key_squares=["d5", "f5", "g6", "c5"]
    ),

    "scandinavian": Opening(
        id="scandinavian",
        name="Scandinavian Defense",
        color=OpeningColor.BLACK,
        response_to="e4",
        description="Challenge e4 immediately with d5! Simple and direct - you get quick development.",
        main_line=[
            OpeningMove(
                "d5",
                "Challenge e4 right away! This is the most direct approach possible.",
                ["exd5", "e5"]
            ),
            OpeningMove(
                "Qxd5",
                "Recapture with your queen. Yes, it comes out early but it's fine in this opening!",
                ["Nc3", "Nf3"]
            ),
            OpeningMove(
                "Qa5",
                "Move your queen to safety. From a5, it watches e5 and the a5-e1 diagonal.",
                ["d4", "Nf3", "Bc4"]
            ),
            OpeningMove(
                "Nf6",
                "Develop your knight naturally. It attacks e4 square.",
                ["Nf3", "Bc4", "d4"]
            ),
            OpeningMove(
                "Bf5",
                "Develop your bishop actively! Like the Caro-Kann, get this out before e6.",
                ["Bc4", "Bd3", "d4"]
            ),
            OpeningMove(
                "c6",
                "Support your queen and prepare for potential d5 later. Very solid.",
                ["Bd2", "Bd3", "d4"]
            ),
            OpeningMove(
                "e6",
                "Prepare to develop your dark-squared bishop. Your center is solid.",
                ["O-O", "Bd3", "Be2"]
            ),
            OpeningMove(
                "Nbd7",
                "Complete development. Your pieces are active and well-coordinated!",
                ["O-O", "Re1", "Qe2"]
            ),
        ],
        typical_plans=[
            "Quick development - you're often ahead in development",
            "Your queen on a5 is safe and active",
            "Aim to castle queenside sometimes for aggressive play",
            "The center is flexible - you can push e5 or c5 later",
        ],
        key_squares=["a5", "f5", "d5", "c6"]
    ),

    "kings_indian": Opening(
        id="kings_indian",
        name="King's Indian Defense",
        color=OpeningColor.BLACK,
        response_to="d4",
        description="Let White build a big center, then strike back! Fianchetto your bishop and attack.",
        main_line=[
            OpeningMove(
                "Nf6",
                "Develop your knight and control e4. This is the start of the King's Indian.",
                ["c4", "Nf3", "Nc3"]
            ),
            OpeningMove(
                "g6",
                "Prepare to fianchetto your bishop. It will be a monster on g7!",
                ["Nc3", "Nf3", "e4"]
            ),
            OpeningMove(
                "Bg7",
                "The fianchetto is complete! Your bishop aims at the center and queenside.",
                ["e4", "Nf3", "Be2"]
            ),
            OpeningMove(
                "d6",
                "Prepare the e5 pawn break. This is the key attacking idea.",
                ["Nf3", "Be2", "f3"]
            ),
            OpeningMove(
                "O-O",
                "Castle immediately for safety. Now you can focus on attacking!",
                ["Be2", "Nf3", "Bg5"]
            ),
            OpeningMove(
                "e5",
                "Strike at the center! This is the main break - you're attacking now.",
                ["d5", "dxe5", "Nf3"]
            ),
            OpeningMove(
                "Nc6",
                "Develop with pressure on d4. You're fighting for the center.",
                ["d5", "Be3", "dxe5"]
            ),
            OpeningMove(
                "Ne7",
                "Reposition your knight! It will support the f5 pawn push - your main attack.",
                ["Nd3", "Be3", "Bg5"]
            ),
        ],
        typical_plans=[
            "Push f5 to start your kingside attack!",
            "After f5, you can push f4 and then g5-g4",
            "Your bishop on g7 supports the entire kingside attack",
            "If White attacks queenside, you attack kingside - it's a race!",
        ],
        key_squares=["g7", "e5", "f5", "f4"]
    ),
}


def get_opening_by_id(opening_id: str) -> Optional[Opening]:
    """Get an opening by its ID."""
    return OPENINGS.get(opening_id)


def get_all_openings() -> List[Opening]:
    """Get all available openings."""
    return list(OPENINGS.values())


def get_openings_for_color(color: str) -> List[Opening]:
    """Get all openings for a specific color."""
    target_color = OpeningColor.WHITE if color == "white" else OpeningColor.BLACK
    return [o for o in OPENINGS.values() if o.color == target_color]


def get_openings_as_black_vs(first_move: str) -> List[Opening]:
    """Get Black openings that respond to a specific first move (e4 or d4)."""
    return [
        o for o in OPENINGS.values()
        if o.color == OpeningColor.BLACK and o.response_to == first_move
    ]
