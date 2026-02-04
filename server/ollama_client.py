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

SYSTEM_PROMPT = """You are a chess opponent. We're playing a game together.

MAKING YOUR MOVE:
- Pick ONE move from the LEGAL MOVES list provided
- Format: **Move: e5** or **Move: Nf6** (use exact notation from the list)
- Briefly explain your thinking (1-2 sentences)

OPENING PRINCIPLES:
- Control center: e5, d5, e6, d6
- Develop knights then bishops: Nf6, Nc6, Bc5, Be7
- Castle early for king safety
- Don't move same piece twice

IF THE PLAYER'S MESSAGE IS UNCLEAR:
- If they seem to want to make a move but you can't understand which one, ask them to clarify with the square (like "e4" or "knight to f3")
- If they ask about the game, answer helpfully
- If they want to undo, acknowledge it
- Never just repeat back what they said

IMPORTANT: Only output your move using **Move: [move]** format. Keep responses short and natural."""


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
        if is_ai_turn:
            # Categorize moves for better selection
            context = f"""[GAME STATE]
{game_context}

[YOUR LEGAL MOVES - pick ONE]:
{', '.join(legal_moves)}

[PLAYER SAYS]: "{user_message}"

RESPOND with **Move: [move]** using EXACTLY one move from the legal moves list above."""
        else:
            context = f"""[GAME STATE]
{game_context}

[PLAYER SAYS]: "{user_message}"

(It's the player's turn - just respond to their message, no move needed from you.)"""

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
        if is_ai_turn:
            context = f"""[GAME STATE]
{game_context}

[YOUR LEGAL MOVES - pick ONE]:
{', '.join(legal_moves)}

[PLAYER SAYS]: "{user_message}"

RESPOND with **Move: [move]** using EXACTLY one move from the legal moves list above."""
        else:
            context = f"""[GAME STATE]
{game_context}

[PLAYER SAYS]: "{user_message}"

(It's the player's turn - just respond to their message, no move needed from you.)"""

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
