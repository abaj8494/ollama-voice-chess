"""
Ollama client for AI chess moves and conversation.
"""

import httpx
import json
import re
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"

SYSTEM_PROMPT = """You are a chess coach and opponent. You play smart chess and help the player learn.

CRITICAL RULES FOR MOVES:
1. When making a move, you MUST include it in this exact format: **Move: [move]**
2. Use standard algebraic notation: e4, Nf3, Bxc6+, O-O (kingside castle), O-O-O (queenside castle)
3. ONLY choose from the legal moves provided - any other move is invalid!

YOUR ROLE:
- Play thoughtful, instructive chess - not too easy, not crushing
- Explain your thinking briefly (1-2 sentences)
- If asked questions, be helpful and encouraging
- When the player makes mistakes, gently point out what they missed
- Keep responses concise since they'll be spoken aloud

RESPONDING TO QUESTIONS:
- "How many moves?" - Tell them the total number of moves played
- "What's the position?" - Describe the key features
- "Undo" / "Take back" - Acknowledge and let them redo
- "Hint" / "Help" - Give a gentle nudge without giving it away
- General chat - Be friendly and conversational

IMPORTANT: When it's your turn, you MUST include **Move: [move]** with a legal move from the provided list."""


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = "llama3.2"):
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

    async def chat(
        self,
        user_message: str,
        game_context: str,
        conversation_history: List[Dict[str, str]],
        is_ai_turn: bool,
        legal_moves: List[str],
    ) -> str:
        """
        Send a chat message to Ollama with game context.

        Args:
            user_message: The user's message
            game_context: Current game state description
            conversation_history: Previous conversation messages
            is_ai_turn: Whether it's the AI's turn to move
            legal_moves: List of legal moves in current position

        Returns:
            The AI's response text
        """
        # Build context message
        context = f"""[GAME STATE]
{game_context}
{f"IT'S YOUR TURN. Legal moves: {', '.join(legal_moves[:30])}" if is_ai_turn else "It's the player's turn."}

[PLAYER SAYS]: "{user_message}"

{f"Remember: Include **Move: [move]** with ONE move from the legal moves list above." if is_ai_turn else ""}"""

        # Build messages for API
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # Add conversation history (limit to recent messages)
        for msg in conversation_history[-10:]:
            messages.append(msg)

        messages.append({"role": "user", "content": context})

        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "I'm not sure how to respond.")
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return "Sorry, I had trouble thinking about that move."

        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            return f"Connection error: {str(e)}"

    async def chat_stream(
        self,
        user_message: str,
        game_context: str,
        conversation_history: List[Dict[str, str]],
        is_ai_turn: bool,
        legal_moves: List[str],
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response from Ollama.
        Yields chunks of text as they arrive.
        """
        context = f"""[GAME STATE]
{game_context}
{f"IT'S YOUR TURN. Legal moves: {', '.join(legal_moves[:30])}" if is_ai_turn else "It's the player's turn."}

[PLAYER SAYS]: "{user_message}"

{f"Remember: Include **Move: [move]** with ONE move from the legal moves list above." if is_ai_turn else ""}"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        for msg in conversation_history[-10:]:
            messages.append(msg)

        messages.append({"role": "user", "content": context})

        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            yield f"Connection error: {str(e)}"

    @staticmethod
    def extract_move(text: str) -> Optional[str]:
        """
        Extract a chess move from AI response text.
        Looks for **Move: xxx** pattern first, then other patterns.
        """
        # Standard patterns in order of priority
        patterns = [
            r'\*\*Move:\s*([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)\*\*',
            r'\*\*Move:\s*([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
            r'Move:\s*\*?\*?([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
            r'I\'?(?:ll)?\s+(?:play|move)\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
            r'My move(?:\s+is)?:?\s+([KQRBNP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                move = match.group(1)
                # Normalize castling
                move = move.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
                return move

        return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
