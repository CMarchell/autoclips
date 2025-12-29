"""Configuration management for AutoClips."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class VideoSettings(BaseModel):
    duration_min: int = 30
    duration_max: int = 70
    width: int = 1080
    height: int = 1920
    fps: int = 30
    clips_per_video: int = 10


class CaptionSettings(BaseModel):
    enabled: bool = True
    style: str = "sentence"
    font: str = "arialbd.ttf"
    font_size: int = 60
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 3
    position: str = "bottom"


class HookTextSettings(BaseModel):
    enabled: bool = True
    font_size: int = 90
    duration: float = 3.0
    position: str = "top_center"


class MusicSettings(BaseModel):
    enabled: bool = True
    volume: float = 0.15
    fade_in: float = 1.0
    fade_out: float = 2.0


class AISettings(BaseModel):
    default_provider: str = "anthropic"
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    temperature: float = 0.8


class ElevenLabsSettings(BaseModel):
    model_id: str = "eleven_multilingual_v2"
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True


class PexelsSettings(BaseModel):
    per_page: int = 15
    min_duration: int = 5
    orientation: str = "portrait"


class DeduplicationSettings(BaseModel):
    topic_cooldown_days: int = 30
    footage_cooldown_count: int = 10


class PathSettings(BaseModel):
    projects: str = "projects"
    output: str = "output"
    assets: str = "assets"
    database: str = "data/autoclips.db"


class Settings(BaseSettings):
    """Main settings loaded from environment and config files."""

    # API Keys (from environment)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    pexels_api_key: str = ""

    # Provider override
    ai_provider: str = "anthropic"

    # Nested settings (loaded from YAML)
    video: VideoSettings = VideoSettings()
    captions: CaptionSettings = CaptionSettings()
    hook_text: HookTextSettings = HookTextSettings()
    music: MusicSettings = MusicSettings()
    ai: AISettings = AISettings()
    elevenlabs: ElevenLabsSettings = ElevenLabsSettings()
    pexels: PexelsSettings = PexelsSettings()
    deduplication: DeduplicationSettings = DeduplicationSettings()
    paths: PathSettings = PathSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from environment and YAML config."""
        # Start with environment variables
        instance = cls()

        # Load YAML config if it exists
        config_path = Path("config/settings.yaml")
        if config_path.exists():
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f) or {}

            # Update nested settings from YAML
            if "video" in yaml_config:
                instance.video = VideoSettings(**yaml_config["video"])
            if "captions" in yaml_config:
                instance.captions = CaptionSettings(**yaml_config["captions"])
            if "hook_text" in yaml_config:
                instance.hook_text = HookTextSettings(**yaml_config["hook_text"])
            if "music" in yaml_config:
                instance.music = MusicSettings(**yaml_config["music"])
            if "ai" in yaml_config:
                instance.ai = AISettings(**yaml_config["ai"])
            if "elevenlabs" in yaml_config:
                instance.elevenlabs = ElevenLabsSettings(**yaml_config["elevenlabs"])
            if "pexels" in yaml_config:
                instance.pexels = PexelsSettings(**yaml_config["pexels"])
            if "deduplication" in yaml_config:
                instance.deduplication = DeduplicationSettings(**yaml_config["deduplication"])
            if "paths" in yaml_config:
                instance.paths = PathSettings(**yaml_config["paths"])

        return instance


# Global settings instance
settings = Settings.load()


def get_niche_config(niche: str | None = None) -> dict[str, Any]:
    """Load niche-specific configuration.

    Args:
        niche: Niche name (e.g., 'finance'). If None, uses _default.

    Returns:
        Niche configuration dictionary.
    """
    niche = niche or "_default"
    niche_path = Path(f"config/niches/{niche}.yaml")

    # Fall back to default if niche not found
    if not niche_path.exists():
        niche_path = Path("config/niches/_default.yaml")

    if not niche_path.exists():
        return {}

    with open(niche_path) as f:
        return yaml.safe_load(f) or {}


def get_voice_config(voice_key: str | None = None) -> dict[str, Any]:
    """Load voice configuration from voices.yaml.

    Args:
        voice_key: Voice key (e.g., 'adam'). If None, returns all voices.

    Returns:
        Voice configuration dictionary.
    """
    voices_path = Path("config/voices.yaml")
    if not voices_path.exists():
        return {}

    with open(voices_path) as f:
        voices_config = yaml.safe_load(f) or {}

    if voice_key is None:
        return voices_config

    voices = voices_config.get("voices", {})
    return voices.get(voice_key, {})


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path.cwd()


def get_projects_dir() -> Path:
    """Get the projects directory path."""
    return get_project_root() / settings.paths.projects


def get_output_dir() -> Path:
    """Get the output directory path."""
    return get_project_root() / settings.paths.output


def get_assets_dir() -> Path:
    """Get the assets directory path."""
    return get_project_root() / settings.paths.assets


def get_database_path() -> Path:
    """Get the database file path."""
    return get_project_root() / settings.paths.database
