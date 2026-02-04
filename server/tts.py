"""
Neural Text-to-Speech using Microsoft Edge TTS.

Provides high-quality, natural-sounding voices without API keys.
"""

import edge_tts
import asyncio
import logging
import io
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# High-quality neural voices
VOICES = {
    "guy": "en-US-GuyNeural",         # American male, warm
    "jenny": "en-US-JennyNeural",     # American female, friendly
    "ryan": "en-GB-RyanNeural",       # British male, sophisticated
    "sonia": "en-GB-SoniaNeural",     # British female, clear
    "tony": "en-US-TonyNeural",       # American male, casual
    "aria": "en-US-AriaNeural",       # American female, expressive
    "davis": "en-US-DavisNeural",     # American male, authoritative
    "jane": "en-US-JaneNeural",       # American female, professional
}

DEFAULT_VOICE = "ryan"  # British male - sounds great for chess


async def text_to_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> bytes:
    """
    Convert text to speech using Edge TTS.

    Args:
        text: The text to speak
        voice: Voice key from VOICES dict or full voice name
        rate: Speech rate adjustment (e.g., "+10%", "-20%")
        pitch: Pitch adjustment (e.g., "+5Hz", "-10Hz")

    Returns:
        MP3 audio data as bytes
    """
    # Get voice name
    voice_name = VOICES.get(voice, voice)

    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=rate, pitch=pitch)

        # Collect audio chunks
        audio_data = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.write(chunk["data"])

        return audio_data.getvalue()

    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise


async def list_voices(language: str = "en") -> List[Dict]:
    """
    List available voices for a language.

    Returns list of voice info dicts with name, gender, locale.
    """
    try:
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v["ShortName"],
                "display": v["FriendlyName"],
                "gender": v["Gender"],
                "locale": v["Locale"]
            }
            for v in voices
            if v["Locale"].startswith(language)
        ]
    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        return []


def get_voice_options() -> List[Dict]:
    """Get the curated list of high-quality voices."""
    return [
        {"key": "ryan", "name": "Ryan (British Male)", "description": "Sophisticated, clear"},
        {"key": "sonia", "name": "Sonia (British Female)", "description": "Warm, articulate"},
        {"key": "guy", "name": "Guy (American Male)", "description": "Friendly, natural"},
        {"key": "jenny", "name": "Jenny (American Female)", "description": "Energetic, expressive"},
        {"key": "davis", "name": "Davis (American Male)", "description": "Deep, authoritative"},
        {"key": "aria", "name": "Aria (American Female)", "description": "Conversational"},
        {"key": "tony", "name": "Tony (American Male)", "description": "Casual, relaxed"},
        {"key": "jane", "name": "Jane (American Female)", "description": "Professional, clear"},
    ]
