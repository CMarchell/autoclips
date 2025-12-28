"""Generate voiceovers using ElevenLabs API."""

from pathlib import Path
from typing import Optional

import httpx

from ..core.config import get_niche_config, get_voice_config, settings


def generate_voiceover(
    text: str,
    output_path: Path,
    voice_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    niche: Optional[str] = None,
) -> dict[str, any]:
    """Generate a voiceover using ElevenLabs.

    Args:
        text: The script text to convert to speech
        output_path: Where to save the audio file
        voice_key: Voice key from voices.yaml (e.g., 'adam')
        voice_id: Direct ElevenLabs voice ID (overrides voice_key)
        niche: Niche to get default voice from

    Returns:
        Dict with 'path', 'duration', 'voice_id', 'voice_name'
    """
    # Resolve voice ID
    actual_voice_id = voice_id
    voice_name = None

    if not actual_voice_id:
        if voice_key:
            voice_config = get_voice_config(voice_key)
            actual_voice_id = voice_config.get("voice_id")
            voice_name = voice_config.get("name", voice_key)
        elif niche:
            # Get default voice for niche
            niche_config = get_niche_config(niche)
            niche_voice_key = niche_config.get("voice", {}).get("voice_key")
            if niche_voice_key:
                voice_config = get_voice_config(niche_voice_key)
                actual_voice_id = voice_config.get("voice_id")
                voice_name = voice_config.get("name", niche_voice_key)

    # Fallback to default
    if not actual_voice_id:
        voices_config = get_voice_config()
        default_key = voices_config.get("defaults", {}).get("generic", "sam")
        voice_config = get_voice_config(default_key)
        actual_voice_id = voice_config.get("voice_id", "yoZ06aMxZJJ28mfd3POQ")
        voice_name = voice_config.get("name", "Sam")

    # Get voice settings
    el_settings = settings.elevenlabs

    # Make API request
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{actual_voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.elevenlabs_api_key,
    }

    payload = {
        "text": text,
        "model_id": el_settings.model_id,
        "voice_settings": {
            "stability": el_settings.stability,
            "similarity_boost": el_settings.similarity_boost,
            "style": el_settings.style,
            "use_speaker_boost": el_settings.use_speaker_boost,
        },
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Save audio file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

    # Get audio duration
    duration = get_audio_duration(output_path)

    return {
        "path": output_path,
        "duration": duration,
        "voice_id": actual_voice_id,
        "voice_name": voice_name,
    }


def get_audio_duration(audio_path: Path) -> float:
    """Get the duration of an audio file in seconds.

    Args:
        audio_path: Path to the audio file

    Returns:
        Duration in seconds
    """
    try:
        from moviepy.editor import AudioFileClip

        with AudioFileClip(str(audio_path)) as audio:
            return audio.duration
    except Exception:
        # Fallback: estimate from file size (rough)
        # MP3 at ~128kbps = ~16KB per second
        file_size = audio_path.stat().st_size
        return file_size / 16000


def list_available_voices() -> list[dict[str, str]]:
    """List all available voices from the configuration.

    Returns:
        List of voice info dicts
    """
    voices_config = get_voice_config()
    voices = voices_config.get("voices", {})

    return [
        {
            "key": key,
            "name": config.get("name", key),
            "description": config.get("description", ""),
            "gender": config.get("gender", ""),
            "tone": config.get("tone", ""),
        }
        for key, config in voices.items()
    ]


def preview_voice(
    voice_key: str,
    text: str = "Hello! This is a preview of my voice. I hope you like it!",
) -> bytes:
    """Generate a quick voice preview without saving.

    Args:
        voice_key: Voice key from voices.yaml
        text: Sample text to speak

    Returns:
        Audio bytes (MP3)
    """
    voice_config = get_voice_config(voice_key)
    voice_id = voice_config.get("voice_id")

    if not voice_id:
        raise ValueError(f"Unknown voice: {voice_key}")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.elevenlabs_api_key,
    }

    payload = {
        "text": text,
        "model_id": settings.elevenlabs.model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.content
