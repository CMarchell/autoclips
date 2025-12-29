"""Generate voiceovers using ElevenLabs API."""

import json
from pathlib import Path
from typing import Any, Optional

from elevenlabs import ElevenLabs, VoiceSettings

from ..core.config import get_niche_config, get_voice_config, settings


def _get_client() -> ElevenLabs:
    """Get an ElevenLabs client instance."""
    return ElevenLabs(api_key=settings.elevenlabs_api_key)


def generate_voiceover(
    text: str,
    output_path: Path,
    voice_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    niche: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a voiceover using ElevenLabs with word timestamps.

    Args:
        text: The script text to convert to speech
        output_path: Where to save the audio file
        voice_key: Voice key from voices.yaml (e.g., 'adam')
        voice_id: Direct ElevenLabs voice ID (overrides voice_key)
        niche: Niche to get default voice from

    Returns:
        Dict with 'path', 'duration', 'voice_id', 'voice_name', 'word_timestamps'
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

    # Create client and generate audio with timestamps
    client = _get_client()

    voice_settings = VoiceSettings(
        stability=el_settings.stability,
        similarity_boost=el_settings.similarity_boost,
        style=el_settings.style,
        use_speaker_boost=el_settings.use_speaker_boost,
    )

    # Generate audio WITH timestamps for caption sync
    response = client.text_to_speech.convert_with_timestamps(
        voice_id=actual_voice_id,
        text=text,
        model_id=el_settings.model_id,
        voice_settings=voice_settings,
    )

    # Save audio file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # The response contains audio_base_64 and alignment data
    import base64
    audio_bytes = base64.b64decode(response.audio_base_64)

    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    # Extract word timestamps from alignment data
    word_timestamps = []
    if response.alignment:
        chars = response.alignment.characters
        char_starts = response.alignment.character_start_times_seconds
        char_ends = response.alignment.character_end_times_seconds

        # Build words from characters
        current_word = ""
        word_start = None
        word_end = None

        for i, char in enumerate(chars):
            if char == " " or i == len(chars) - 1:
                # End of word
                if i == len(chars) - 1 and char != " ":
                    current_word += char
                    word_end = char_ends[i]

                if current_word.strip():
                    word_timestamps.append({
                        "word": current_word.strip(),
                        "start": word_start,
                        "end": word_end,
                    })
                current_word = ""
                word_start = None
            else:
                if word_start is None:
                    word_start = char_starts[i]
                current_word += char
                word_end = char_ends[i]

    # Save timestamps alongside audio
    timestamps_path = output_path.with_suffix(".timestamps.json")
    with open(timestamps_path, "w") as f:
        json.dump(word_timestamps, f, indent=2)

    # Get audio duration
    duration = get_audio_duration(output_path)

    return {
        "path": output_path,
        "duration": duration,
        "voice_id": actual_voice_id,
        "voice_name": voice_name,
        "word_timestamps": word_timestamps,
        "timestamps_path": timestamps_path,
    }


def get_audio_duration(audio_path: Path) -> float:
    """Get the duration of an audio file in seconds.

    Args:
        audio_path: Path to the audio file

    Returns:
        Duration in seconds
    """
    try:
        from moviepy import AudioFileClip

        with AudioFileClip(str(audio_path)) as audio:
            return audio.duration
    except Exception:
        # Fallback: estimate from file size (rough)
        # MP3 at ~128kbps = ~16KB per second
        file_size = audio_path.stat().st_size
        return file_size / 16000


def load_timestamps(audio_path: Path) -> list[dict]:
    """Load word timestamps from JSON file.

    Args:
        audio_path: Path to the audio file (timestamps file is derived from this)

    Returns:
        List of word timestamp dicts with 'word', 'start', 'end' keys
    """
    timestamps_path = audio_path.with_suffix(".timestamps.json")
    if timestamps_path.exists():
        with open(timestamps_path) as f:
            return json.load(f)
    return []


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


def list_elevenlabs_voices() -> list[dict[str, str]]:
    """List all available voices from ElevenLabs API.

    Returns:
        List of voice info dicts from the API
    """
    client = _get_client()
    response = client.voices.get_all()

    return [
        {
            "voice_id": voice.voice_id,
            "name": voice.name,
            "category": voice.category,
            "description": voice.description or "",
        }
        for voice in response.voices
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

    client = _get_client()

    audio_generator = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=settings.elevenlabs.model_id,
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
        ),
    )

    # Collect all chunks
    audio_bytes = b"".join(audio_generator)
    return audio_bytes
