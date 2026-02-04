#!/usr/bin/env python3
"""
Text-based debug interface for Voice Chess.
Useful for testing the game logic and AI without the browser.

Usage:
    python -m server.debug_cli
    python -m server.debug_cli --model llama3.1
"""

import asyncio
import argparse
import sys
import re
from typing import Optional

from .game import ChessGame
from .ollama_client import OllamaClient


class DebugCLI:
    """Text-based interface for debugging the chess system."""

    def __init__(self, model: str = "llama3.2"):
        self.game = ChessGame()
        self.client = OllamaClient(model=model)
        self.player_color = "white"

    async def check_ollama(self) -> bool:
        """Check if Ollama is available."""
        return await self.client.check_connection()

    def display_board(self):
        """Display the current board state."""
        state = self.game.state.to_dict()

        print("\n" + "=" * 40)
        print(f"  Position: {self.game.get_formatted_history() or 'Starting position'}")
        print(f"  Turn: {'White' if state['turn'] == 'white' else 'Black'}")
        print(f"  Moves played: {state['half_moves']}")

        if state['is_check']:
            print("  STATUS: CHECK!")
        if state['is_checkmate']:
            print("  STATUS: CHECKMATE!")
        if state['is_stalemate']:
            print("  STATUS: STALEMATE!")
        if state['is_game_over']:
            print(f"  Result: {state['result']}")

        print("=" * 40)

        # Simple ASCII board
        board = self.game.state.board
        print("\n    a b c d e f g h")
        print("  +" + "-" * 17 + "+")

        for rank in range(7, -1, -1):
            row = f"{rank + 1} |"
            for file in range(8):
                square = rank * 8 + file
                piece = board.piece_at(square)
                if piece:
                    symbol = piece.symbol()
                    # Make it more readable
                    row += f" {symbol}"
                else:
                    row += " ."
            row += f" | {rank + 1}"
            print(row)

        print("  +" + "-" * 17 + "+")
        print("    a b c d e f g h\n")

    def is_player_turn(self) -> bool:
        """Check if it's the player's turn."""
        current = self.game.state.to_dict()['turn']
        return current == self.player_color

    def is_ai_turn(self) -> bool:
        """Check if it's the AI's turn."""
        return not self.is_player_turn()

    async def ai_move(self, context_message: str = "Your turn.") -> Optional[str]:
        """Get AI to make a move."""
        if self.game.state.board.is_game_over():
            return None

        state = self.game.state.to_dict()
        ai_color = "Black" if self.player_color == "white" else "White"

        game_context = f"""You are playing as {ai_color}.
The human is playing {self.player_color.title()}.
{self.game.get_formatted_history() or 'No moves yet.'}
{self.game.get_position_description()}"""

        legal_moves = self.game.get_legal_moves()

        print(f"\n[AI thinking...]")

        response = await self.client.chat(
            user_message=context_message,
            game_context=game_context,
            conversation_history=self.game.get_conversation_history(),
            is_ai_turn=True,
            legal_moves=legal_moves
        )

        # Store in history
        self.game.add_conversation("user", context_message)
        self.game.add_conversation("assistant", response)

        # Extract and make move
        extracted = OllamaClient.extract_move(response)
        ai_move = None

        if extracted:
            result = self.game.make_move(extracted)
            if result["success"]:
                ai_move = result["move"]
            else:
                print(f"[AI suggested invalid move: {extracted}]")
                # Fallback to first legal move
                if legal_moves:
                    fallback = legal_moves[0]
                    result = self.game.make_move(fallback)
                    if result["success"]:
                        ai_move = result["move"]
                        response += f"\n(Fallback move: {ai_move})"

        # Clean response for display
        clean = re.sub(r'\*\*Move:\s*[^*]+\*\*', '', response)
        clean = re.sub(r'\*\*', '', clean).strip()

        print(f"\n[AI ({ai_color})]: {clean}")
        if ai_move:
            print(f"[Move: {ai_move}]")

        return ai_move

    async def chat(self, message: str) -> str:
        """Send a chat message to the AI (no move expected)."""
        state = self.game.state.to_dict()
        ai_color = "Black" if self.player_color == "white" else "White"

        game_context = f"""You are playing as {ai_color}.
The human is playing {self.player_color.title()}.
{self.game.get_formatted_history() or 'No moves yet.'}
{self.game.get_position_description()}"""

        response = await self.client.chat(
            user_message=message,
            game_context=game_context,
            conversation_history=self.game.get_conversation_history(),
            is_ai_turn=False,
            legal_moves=self.game.get_legal_moves()
        )

        self.game.add_conversation("user", message)
        self.game.add_conversation("assistant", response)

        clean = re.sub(r'\*\*', '', response).strip()
        print(f"\n[AI]: {clean}")

        return response

    def player_move(self, move_str: str) -> bool:
        """Make a player move."""
        result = self.game.make_move(move_str)
        if result["success"]:
            print(f"[Your move: {result['move']}]")
            return True
        else:
            print(f"[Invalid move: {result['error']}]")
            return False

    def undo(self):
        """Undo last move pair."""
        result = self.game.undo_last_pair()
        if result["success"]:
            print(f"[Undone moves: {result['undone_moves']}]")
        else:
            print("[Nothing to undo]")

    async def run(self):
        """Main loop."""
        print("\n" + "=" * 50)
        print("       VOICE CHESS - Debug CLI")
        print("=" * 50)

        if not await self.check_ollama():
            print("\n[ERROR] Cannot connect to Ollama!")
            print("Make sure Ollama is running: ollama serve")
            return

        print(f"\n[Connected to Ollama, using model: {self.client.model}]")

        # Choose color
        print("\nChoose your color:")
        print("  [w] White (you move first)")
        print("  [b] Black (AI moves first)")

        while True:
            choice = input("\nYour choice (w/b): ").strip().lower()
            if choice in ['w', 'white']:
                self.player_color = "white"
                break
            elif choice in ['b', 'black']:
                self.player_color = "black"
                break
            print("Please enter 'w' or 'b'")

        self.game.new_game(self.player_color)
        print(f"\n[You are playing as {self.player_color.upper()}]")

        print("\nCommands:")
        print("  <move>   - Make a move (e4, Nf3, O-O, etc.)")
        print("  /board   - Show the board")
        print("  /moves   - Show move history")
        print("  /legal   - Show legal moves")
        print("  /undo    - Undo last move pair")
        print("  /chat    - Chat with AI (no move)")
        print("  /pgn     - Show PGN")
        print("  /quit    - Exit")

        self.display_board()

        # If player is black, AI moves first
        if self.player_color == "black":
            await self.ai_move("You are White. Make your opening move.")
            self.display_board()

        # Main loop
        while not self.game.state.board.is_game_over():
            try:
                prompt = f"[{'Your' if self.is_player_turn() else 'AI'} turn] > "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() == "/quit":
                    print("\n[Game ended]")
                    break

                elif user_input.lower() == "/board":
                    self.display_board()
                    continue

                elif user_input.lower() == "/moves":
                    print(f"\n{self.game.get_formatted_history() or 'No moves yet.'}")
                    continue

                elif user_input.lower() == "/legal":
                    moves = self.game.get_legal_moves()
                    print(f"\nLegal moves ({len(moves)}): {', '.join(moves)}")
                    continue

                elif user_input.lower() == "/undo":
                    self.undo()
                    self.display_board()
                    continue

                elif user_input.lower() == "/pgn":
                    print(f"\n{self.game.get_pgn()}")
                    continue

                elif user_input.lower().startswith("/chat "):
                    message = user_input[6:].strip()
                    if message:
                        await self.chat(message)
                    continue

                elif user_input.startswith("/"):
                    print("[Unknown command]")
                    continue

                # Try as a move
                if self.is_player_turn():
                    if self.player_move(user_input):
                        self.display_board()

                        # AI responds
                        if not self.game.state.board.is_game_over():
                            await self.ai_move(f"I played {user_input}.")
                            self.display_board()
                else:
                    print("[It's the AI's turn, not yours]")

            except KeyboardInterrupt:
                print("\n\n[Interrupted]")
                break
            except EOFError:
                break

        # Game over
        if self.game.state.board.is_game_over():
            self.display_board()
            state = self.game.state.to_dict()
            print(f"\n[GAME OVER: {state['result']}]")
            print(f"\nFinal PGN:\n{self.game.get_pgn()}")

        await self.client.close()


async def main():
    parser = argparse.ArgumentParser(description="Debug CLI for Voice Chess")
    parser.add_argument("--model", "-m", default="llama3.2", help="Ollama model")
    args = parser.parse_args()

    cli = DebugCLI(model=args.model)
    await cli.run()


def main_sync():
    """Synchronous wrapper for entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
