"""Project state management for video generation pipeline."""

import json
import shutil
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .config import get_output_dir, get_projects_dir


class ProjectStatus(str, Enum):
    """Video project status."""

    DRAFT = "draft"
    PREVIEW = "preview"
    APPROVED = "approved"
    KILLED = "killed"


class FootageClip(BaseModel):
    """Represents a footage clip in the project."""

    filename: str
    pexels_id: int
    keyword: str
    duration: float
    start_time: Optional[float] = None  # When it starts in the video
    url: Optional[str] = None


class TimelineEntry(BaseModel):
    """Entry in the video timeline."""

    clip_filename: str
    start: float
    end: float
    keyword: str


class ProjectState(BaseModel):
    """Full project state saved to project.json."""

    id: str
    topic: str
    niche: Optional[str] = None
    status: ProjectStatus = ProjectStatus.DRAFT

    # Settings used
    voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    music_track: Optional[str] = None
    music_mood: Optional[str] = None

    # Generated content
    script: Optional[str] = None
    hook_text: Optional[str] = None
    duration: Optional[float] = None
    word_count: Optional[int] = None

    # Footage
    footage_clips: list[FootageClip] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class ProjectMetadata(BaseModel):
    """Metadata for the video (titles, descriptions, tags)."""

    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)

    # Platform-specific (optional)
    tiktok_caption: Optional[str] = None
    youtube_title: Optional[str] = None
    youtube_description: Optional[str] = None
    instagram_caption: Optional[str] = None


class Project:
    """Manages a single video project's files and state."""

    def __init__(self, project_id: str):
        self.id = project_id
        self.path = get_projects_dir() / project_id
        self._state: Optional[ProjectState] = None

    @classmethod
    def create(cls, topic: str, niche: Optional[str] = None) -> "Project":
        """Create a new project with a unique ID."""
        # Generate ID: date_slug_uuid
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = cls._slugify(topic)[:30]
        short_uuid = uuid.uuid4().hex[:8]
        project_id = f"{date_str}_{slug}_{short_uuid}"

        project = cls(project_id)
        project._create_directory_structure()

        # Initialize state
        project._state = ProjectState(
            id=project_id,
            topic=topic,
            niche=niche,
        )
        project.save_state()

        return project

    @classmethod
    def load(cls, project_id: str) -> Optional["Project"]:
        """Load an existing project by ID."""
        project = cls(project_id)
        if not project.path.exists():
            return None
        project._load_state()
        return project

    @classmethod
    def list_all(cls, status: Optional[ProjectStatus] = None) -> list["Project"]:
        """List all projects, optionally filtered by status."""
        projects_dir = get_projects_dir()
        if not projects_dir.exists():
            return []

        projects = []
        for path in projects_dir.iterdir():
            if path.is_dir() and (path / "project.json").exists():
                project = cls.load(path.name)
                if project:
                    if status is None or project.state.status == status:
                        projects.append(project)

        # Sort by creation date, newest first
        projects.sort(key=lambda p: p.state.created_at, reverse=True)
        return projects

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a URL-friendly slug."""
        import re

        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text.strip("-")

    def _create_directory_structure(self):
        """Create the project directory structure."""
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "footage").mkdir(exist_ok=True)

    def _load_state(self):
        """Load state from project.json."""
        state_path = self.path / "project.json"
        if state_path.exists():
            with open(state_path) as f:
                data = json.load(f)
            self._state = ProjectState(**data)

    @property
    def state(self) -> ProjectState:
        """Get the current project state."""
        if self._state is None:
            self._load_state()
        if self._state is None:
            raise ValueError(f"Project {self.id} has no state")
        return self._state

    def save_state(self):
        """Save state to project.json."""
        self.state.updated_at = datetime.utcnow()
        state_path = self.path / "project.json"
        with open(state_path, "w") as f:
            json.dump(self.state.model_dump(mode="json"), f, indent=2, default=str)

    # File paths
    @property
    def script_path(self) -> Path:
        return self.path / "script.txt"

    @property
    def voiceover_path(self) -> Path:
        return self.path / "voiceover.mp3"

    @property
    def timeline_path(self) -> Path:
        return self.path / "timeline.json"

    @property
    def metadata_path(self) -> Path:
        return self.path / "metadata.json"

    @property
    def preview_path(self) -> Path:
        return self.path / "preview.mp4"

    @property
    def final_path(self) -> Path:
        return self.path / "final.mp4"

    @property
    def footage_dir(self) -> Path:
        return self.path / "footage"

    # Script operations
    def get_script(self) -> Optional[str]:
        """Get the current script."""
        if self.script_path.exists():
            return self.script_path.read_text(encoding="utf-8")
        return self.state.script

    def set_script(self, script: str):
        """Set the script content."""
        self.script_path.write_text(script, encoding="utf-8")
        self._state.script = script

        # Calculate word count and estimated duration
        words = len(script.split())
        self._state.word_count = words
        # Assume ~2.5 words per second for speaking pace
        self._state.duration = words / 2.5

        self.save_state()

    def update_script_section(self, find: str, replace: str) -> bool:
        """Find and replace text in the script."""
        script = self.get_script()
        if script and find in script:
            new_script = script.replace(find, replace)
            self.set_script(new_script)
            return True
        return False

    # Footage operations
    def add_footage(self, clip: FootageClip):
        """Add a footage clip to the project."""
        self._state.footage_clips.append(clip)
        self.save_state()

    def remove_footage(self, filename: Optional[str] = None, keyword: Optional[str] = None) -> bool:
        """Remove footage by filename or keyword."""
        removed = False
        new_clips = []

        for clip in self.state.footage_clips:
            should_remove = False
            if filename and clip.filename == filename:
                should_remove = True
            elif keyword and keyword.lower() in clip.keyword.lower():
                should_remove = True

            if should_remove:
                # Delete the file if it exists
                clip_path = self.footage_dir / clip.filename
                if clip_path.exists():
                    clip_path.unlink()
                removed = True
            else:
                new_clips.append(clip)

        self._state.footage_clips = new_clips
        self.save_state()
        return removed

    def get_footage_list(self) -> list[dict[str, Any]]:
        """Get a list of footage clips with details."""
        return [
            {
                "filename": clip.filename,
                "keyword": clip.keyword,
                "pexels_id": clip.pexels_id,
                "duration": clip.duration,
            }
            for clip in self.state.footage_clips
        ]

    # Timeline operations
    def set_timeline(self, timeline: list[TimelineEntry]):
        """Set the video timeline."""
        self._state.timeline = timeline
        # Save timeline to JSON file for easy inspection
        with open(self.timeline_path, "w") as f:
            json.dump([t.model_dump() for t in timeline], f, indent=2)
        self.save_state()

    def get_timeline(self) -> list[TimelineEntry]:
        """Get the current timeline."""
        if self.timeline_path.exists():
            with open(self.timeline_path) as f:
                data = json.load(f)
            return [TimelineEntry(**entry) for entry in data]
        return self.state.timeline

    # Metadata operations
    def get_metadata(self) -> Optional[ProjectMetadata]:
        """Get project metadata."""
        if self.metadata_path.exists():
            with open(self.metadata_path) as f:
                data = json.load(f)
            return ProjectMetadata(**data)
        return None

    def set_metadata(self, metadata: ProjectMetadata):
        """Set project metadata."""
        with open(self.metadata_path, "w") as f:
            json.dump(metadata.model_dump(), f, indent=2)

    # Voice and music
    def set_voice(self, voice_id: str, voice_name: Optional[str] = None):
        """Set the voice for this project."""
        self._state.voice_id = voice_id
        self._state.voice_name = voice_name
        self.save_state()

    def set_music(self, track_path: str, mood: Optional[str] = None):
        """Set the background music for this project."""
        self._state.music_track = track_path
        self._state.music_mood = mood
        self.save_state()

    # Status management
    def set_status(self, status: ProjectStatus):
        """Update project status."""
        self._state.status = status
        if status == ProjectStatus.APPROVED:
            self._state.approved_at = datetime.utcnow()
        self.save_state()

    def approve(self) -> Path:
        """Approve the project and move final video to output."""
        self.set_status(ProjectStatus.APPROVED)

        # Copy final video to output directory
        output_dir = get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.final_path.exists():
            output_path = output_dir / f"{self.id}.mp4"
            shutil.copy2(self.final_path, output_path)

            # Also copy metadata
            if self.metadata_path.exists():
                metadata_output = output_dir / f"{self.id}_metadata.json"
                shutil.copy2(self.metadata_path, metadata_output)

            return output_path
        return self.final_path

    def kill(self):
        """Mark project as killed and clean up."""
        self.set_status(ProjectStatus.KILLED)
        # Optionally delete files (keep state for records)
        # For now, just mark as killed

    def delete(self):
        """Permanently delete the project."""
        if self.path.exists():
            shutil.rmtree(self.path)

    # Summary for agent inspection
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the project for agent inspection."""
        return {
            "id": self.id,
            "topic": self.state.topic,
            "niche": self.state.niche,
            "status": self.state.status,
            "script_preview": (self.get_script() or "")[:200] + "..."
            if self.get_script()
            else None,
            "word_count": self.state.word_count,
            "estimated_duration": self.state.duration,
            "footage_count": len(self.state.footage_clips),
            "voice": self.state.voice_name,
            "music": self.state.music_mood,
            "has_preview": self.preview_path.exists(),
            "has_final": self.final_path.exists(),
            "created_at": self.state.created_at.isoformat(),
        }
