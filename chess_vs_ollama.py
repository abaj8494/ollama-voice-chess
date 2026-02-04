#!/usr/bin/env python3
"""
Chess vs Ollama - A conversational chess game against your local LLM
"""

import requests
import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:70b"  # Change this to your preferred model
GAMES_DIR = Path("./chess_games")

SYSTEM_PROMPT = """You are a grandmaster-level chess player. You play STRONG, aggressive chess and aim to WIN.

CRITICAL RULES:
1. When making a move, you MUST include it in this exact format: **Move: [your move]**
2. Use standard algebraic notation: e4, Nf3, Bxc6+, O-O (kingside castle), O-O-O (queenside castle), e8=Q (promotion)
3. THINK DEEPLY before each move. Consider tactics, strategy, and your opponent's threats.

CHESS PRINCIPLES TO FOLLOW:
- Look for TACTICS first: pins, forks, skewers, discovered attacks, back rank mates
- Control the center, develop pieces, castle early
- In middlegame: create threats, attack weaknesses, improve worst piece
- In endgame: activate king, create passed pawns

When you analyze, share your reasoning:
- What threats exist?
- What's your plan?
- Why this move?

You can chat naturally about chess, the game, or anything else. But when it's your turn, ALWAYS include **Move: [move]** in your response.

Be confident. If you spot a mistake, PUNISH IT."""


class ChessGame:
    def __init__(self, model=MODEL):
        self.model = model
        self.move_history = []
        self.conversation_history = []
        self.player_color = "white"
        self.games_dir = GAMES_DIR
        self.games_dir.mkdir(exist_ok=True)
        
    def check_ollama(self):
        """Check if Ollama is running"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self):
        """List available Ollama models"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return [m["name"] for m in models]
        except:
            pass
        return []

    def get_game_context(self):
        """Build current game state for the LLM"""
        if not self.move_history:
            return "No moves yet. The game is just starting."
        
        pgn = ""
        for i, move in enumerate(self.move_history):
            if i % 2 == 0:
                pgn += f"{i//2 + 1}. "
            pgn += move + " "
        
        whose_turn = "White" if len(self.move_history) % 2 == 0 else "Black"
        ai_color = "Black" if self.player_color == "white" else "White"
        
        return f"""Current game: {pgn.strip()}

Move {len(self.move_history) + 1}. {whose_turn} to move.
You are playing as {ai_color}."""

    def send_message(self, user_message):
        """Send a message to Ollama and get response"""
        game_context = self.get_game_context()
        ai_color = "Black" if self.player_color == "white" else "White"
        
        # Check if it's AI's turn to move
        is_ai_turn = (len(self.move_history) % 2 == 1 and self.player_color == "white") or \
                     (len(self.move_history) % 2 == 0 and self.player_color == "black")
        
        context_msg = f"""[GAME STATE]
You are {ai_color}. The human is {self.player_color.title()}.
{game_context}
{"IT'S YOUR TURN - you must make a move!" if is_ai_turn else ""}

[HUMAN]: {user_message}"""

        self.conversation_history.append({
            "role": "user",
            "content": context_msg
        })

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *self.conversation_history
                    ],
                    "stream": True
                },
                stream=True,
                timeout=120
            )
            
            full_response = ""
            print(f"\n🤖 {self.model}: ", end="", flush=True)
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    print(chunk, end="", flush=True)
                    full_response += chunk
            
            print("\n")
            
            self.conversation_history.append({
                "role": "assistant", 
                "content": full_response
            })
            
            # Extract move if present
            move = self.extract_move(full_response)
            if move:
                self.move_history.append(move)
                print(f"  ♟️  Move recorded: {move}")
            
            return full_response
            
        except requests.exceptions.ConnectionError:
            print("\n❌ Cannot connect to Ollama. Is it running?")
            return None
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return None

    def extract_move(self, text):
        """Extract chess move from response"""
        import re
        
        # Look for **Move: xxx** pattern
        patterns = [
            r'\*\*Move:\s*([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)\*\*',
            r'\*\*Move:\s*([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
            r'Move:\s*\*?\*?([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
            r'\*\*([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)\*\*',
            r'I (?:play|move)\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def record_player_move(self, move):
        """Record the player's move"""
        self.move_history.append(move)

    def get_pgn(self):
        """Generate PGN for the game"""
        pgn_lines = [
            f'[Event "Chess vs Ollama"]',
            f'[Date "{datetime.now().strftime("%Y.%m.%d")}"]',
            f'[White "{"Human" if self.player_color == "white" else self.model}"]',
            f'[Black "{"Human" if self.player_color == "black" else self.model}"]',
            f'[Model "{self.model}"]',
            ""
        ]
        
        moves_str = ""
        for i, move in enumerate(self.move_history):
            if i % 2 == 0:
                moves_str += f"{i//2 + 1}. "
            moves_str += move + " "
            if i % 10 == 9:
                moves_str += "\n"
        
        pgn_lines.append(moves_str.strip())
        return "\n".join(pgn_lines)

    def save_game(self, result="*"):
        """Save the game to a PGN file"""
        if not self.move_history:
            print("No moves to save.")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.games_dir / f"game_{timestamp}.pgn"
        
        pgn = self.get_pgn()
        if result != "*":
            pgn += f" {result}"
        
        with open(filename, "w") as f:
            f.write(pgn)
        
        print(f"💾 Game saved to: {filename}")
        return filename

    def display_moves(self):
        """Display current move list"""
        if not self.move_history:
            print("No moves yet.")
            return
            
        print("\n📋 Move History:")
        print("-" * 30)
        for i in range(0, len(self.move_history), 2):
            move_num = i // 2 + 1
            white = self.move_history[i]
            black = self.move_history[i + 1] if i + 1 < len(self.move_history) else ""
            print(f"  {move_num:3}. {white:8} {black}")
        print("-" * 30)


def main():
    print("=" * 50)
    print("     ♔ CHESS vs OLLAMA ♚")
    print("     Conversational Chess with Local LLM")
    print("=" * 50)
    
    game = ChessGame()
    
    # Check Ollama connection
    if not game.check_ollama():
        print("\n❌ Cannot connect to Ollama at localhost:11434")
        print("   Make sure Ollama is running: ollama serve")
        return
    
    print("\n✅ Connected to Ollama")
    
    # List and select model
    models = game.list_models()
    if models:
        print(f"\n📦 Available models: {', '.join(models[:10])}")
        print(f"   Current model: {game.model}")
        
        choice = input("\nEnter model name (or press Enter for default): ").strip()
        if choice and choice in models:
            game.model = choice
            print(f"   Using: {game.model}")
        elif choice:
            print(f"   Model '{choice}' not found, using {game.model}")
    
    # Choose color
    print("\n🎨 Choose your color:")
    print("   [w] White (you move first)")
    print("   [b] Black (AI moves first)")
    
    while True:
        color = input("\nYour choice (w/b): ").strip().lower()
        if color in ['w', 'white']:
            game.player_color = "white"
            break
        elif color in ['b', 'black']:
            game.player_color = "black"
            break
        print("Please enter 'w' or 'b'")
    
    print(f"\n✅ You are playing as {game.player_color.upper()}")
    print("\n" + "=" * 50)
    print("COMMANDS:")
    print("  - Type a move: e4, Nf3, O-O, etc.")
    print("  - Chat: just type naturally")
    print("  - /moves  - show move history")
    print("  - /save   - save game to PGN")
    print("  - /resign - resign the game")
    print("  - /quit   - exit without saving")
    print("=" * 50)
    
    # If player is black, AI moves first
    if game.player_color == "black":
        print("\n🤖 AI is thinking about the first move...")
        game.send_message("You are White and move first. Make your opening move.")
    else:
        print("\n♟️  Your move (White):")
    
    # Main game loop
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() == "/quit":
                save = input("Save game before quitting? (y/n): ").strip().lower()
                if save == 'y':
                    game.save_game()
                print("Thanks for playing!")
                break
                
            elif user_input.lower() == "/resign":
                result = "0-1" if game.player_color == "white" else "1-0"
                print(f"\n🏳️  You resigned. {'Black' if game.player_color == 'white' else 'White'} wins!")
                game.save_game(result)
                break
                
            elif user_input.lower() == "/moves":
                game.display_moves()
                continue
                
            elif user_input.lower() == "/save":
                game.save_game()
                continue
            
            # Check if input looks like a chess move
            import re
            move_pattern = r'^([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)$'
            is_move = bool(re.match(move_pattern, user_input, re.IGNORECASE))
            
            if is_move:
                game.record_player_move(user_input)
                print(f"  ♟️  Your move: {user_input}")
                game.send_message(f"I play {user_input}. Your turn.")
            else:
                # Just chatting
                game.send_message(user_input)
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Saving game...")
            game.save_game()
            break
        except EOFError:
            break
    
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()