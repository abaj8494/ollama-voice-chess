"""
Ollama client for chess commentary and tutoring.

Stockfish handles move selection. Ollama explains the moves
and answers strategic questions using Stockfish's analysis.
"""

import httpx
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"

# System prompt for move commentary (brief, spoken aloud)
COMMENTARY_PROMPT = """You are a chess engine's voice. You explain chess moves briefly.

RULES:
- You just played a move. Explain it in ONE short sentence (max 12 words)
- Sound confident and natural, like a skilled player
- Focus on the PURPOSE of the move (attack, defense, development, control)
- Never apologize or express confusion
- Never mention "Stockfish" or "engine" - speak as yourself

GOOD examples:
- "Developing my knight toward the center."
- "Taking that pawn - it was undefended."
- "Castling to safety before the attack."
- "Pinning your knight to the queen."
- "Threatening mate on h7."

BAD examples (never say these):
- "You're right!" / "Sorry!" / "My mistake!"
- "I think..." / "Maybe..." / "Perhaps..."
- Long explanations unless asked"""

# System prompt for tutoring/analysis (detailed explanations)
TUTOR_PROMPT = """You are a chess tutor explaining positions and strategy.

You have access to Stockfish's analysis which shows:
- Position evaluation (positive = white advantage, negative = black advantage)
- Best moves and their expected continuations
- Tactical threats and opportunities

When explaining:
1. Start with who's better and why (material, position, king safety)
2. Point out key features (weak pawns, open files, piece activity)
3. Suggest concrete plans and moves
4. Keep explanations clear and educational

Be direct and confident. Use chess terminology appropriately."""


class OllamaClient:
    """Client for chess commentary and tutoring via Ollama."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = "qwen2.5:14b"):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def check_connection(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama connection check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available Ollama models."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
        return []

    async def explain_move(
        self,
        move: str,
        move_context: str,
        evaluation: str,
        expected_line: List[str],
        position_description: str,
    ) -> str:
        """
        Generate a brief spoken explanation of a chess move.

        Args:
            move: The move played (e.g., "Nf6")
            move_context: What the move does (captures, checks, etc.)
            evaluation: Position evaluation from Stockfish (e.g., "+0.5")
            expected_line: Principal variation (expected continuation)
            position_description: Brief description of the position

        Returns:
            A short, natural explanation suitable for text-to-speech
        """
        # Build context for the LLM
        context = f"""Move played: {move}
What it does: {move_context}
Position eval: {evaluation} (positive = white better)
Expected continuation: {' '.join(expected_line[:4]) if expected_line else 'N/A'}

Generate ONE short sentence (max 12 words) explaining why this move is good.
Do NOT include the move notation in your response - just the explanation."""

        try:
            response = await self._chat(COMMENTARY_PROMPT, context)

            # Clean up response
            response = response.strip()
            response = response.strip('"\'')

            # Remove any move notation that slipped in
            if response.lower().startswith(move.lower()):
                response = response[len(move):].strip(' .,:-')

            # Ensure it's not too long
            if len(response) > 100:
                response = response[:100].rsplit(' ', 1)[0] + '.'

            # Capitalize first letter
            if response:
                response = response[0].upper() + response[1:]

            return response or "Developing my position."

        except Exception as e:
            logger.error(f"Move explanation error: {e}")
            return "Continuing my plan."

    async def answer_question(
        self,
        question: str,
        position_fen: str,
        move_history: str,
        stockfish_analysis: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """
        Answer a chess strategy question using Stockfish analysis.

        Args:
            question: The user's question
            position_fen: Current position in FEN notation
            move_history: Game moves so far
            stockfish_analysis: Analysis from Stockfish including:
                - score: Position evaluation
                - best_moves: Top moves with evaluations
                - is_tactical: Whether position is sharp
            conversation_history: Recent conversation for context

        Returns:
            A detailed, educational response
        """
        # Format the Stockfish analysis for the LLM
        analysis_text = self._format_analysis(stockfish_analysis)

        context = f"""CURRENT POSITION:
Moves so far: {move_history or '(starting position)'}

STOCKFISH ANALYSIS:
{analysis_text}

PLAYER'S QUESTION: "{question}"

Provide a helpful, educational answer. Be specific about moves and plans.
If they ask about a specific move, explain whether it's good or bad and why."""

        try:
            response = await self._chat(
                TUTOR_PROMPT,
                context,
                conversation_history[-4:] if conversation_history else [],
                max_tokens=800  # Allow longer responses for hints/analysis
            )
            return response.strip()

        except Exception as e:
            logger.error(f"Question answering error: {e}")
            return "I'm having trouble analyzing that. Could you rephrase?"

    async def generate_game_over_message(
        self,
        result: str,
        winner: Optional[str],
        move_count: int,
        final_position: str,
    ) -> str:
        """Generate a brief game-over message."""
        if winner:
            context = f"The game ended in {result} after {move_count} moves. {winner} won. Generate a brief, sporting response (1-2 sentences)."
        else:
            context = f"The game ended in a {result} after {move_count} moves. Generate a brief, sporting response (1-2 sentences)."

        try:
            response = await self._chat(COMMENTARY_PROMPT, context)
            return response.strip()
        except:
            if winner == "black":
                return "Well played! You got me this time."
            elif winner == "white":
                return "Good game! I managed to find the win."
            return "A hard-fought draw!"

    def _format_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format Stockfish analysis for the LLM."""
        if not analysis:
            return "No analysis available."

        lines = []

        score = analysis.get('score', '0.0')
        lines.append(f"Evaluation: {score}")

        if score.startswith('M'):
            lines.append("(Forced checkmate detected!)")
        elif score.startswith('-'):
            try:
                val = float(score)
                if val < -2:
                    lines.append("(Black has a significant advantage)")
                elif val < -0.5:
                    lines.append("(Black is slightly better)")
                else:
                    lines.append("(Position is roughly equal)")
            except:
                pass
        else:
            try:
                val = float(score)
                if val > 2:
                    lines.append("(White has a significant advantage)")
                elif val > 0.5:
                    lines.append("(White is slightly better)")
                else:
                    lines.append("(Position is roughly equal)")
            except:
                pass

        best_moves = analysis.get('best_moves', [])
        if best_moves:
            lines.append("\nTop moves:")
            for i, move_info in enumerate(best_moves[:3], 1):
                move = move_info.get('move', '?')
                mv_score = move_info.get('score', '?')
                line = move_info.get('line', [])
                line_str = ' '.join(line[:4]) if line else ''
                lines.append(f"  {i}. {move} (eval: {mv_score}) - {line_str}")

        if analysis.get('is_tactical'):
            lines.append("\n(Position is TACTICAL - forcing moves available)")

        return '\n'.join(lines)

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
        max_tokens: int = 256,
    ) -> str:
        """Internal method to send a chat request to Ollama."""
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history[-6:])

        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": max_tokens,
                    }
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return ""

        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
