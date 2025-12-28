"""Assemble final video from components."""

import random
from pathlib import Path
from typing import Optional

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)

from ..core.config import get_assets_dir, settings
from ..core.project import Project, TimelineEntry
from .captions import generate_word_timestamps, render_captions, render_hook_text


def assemble_video(project: Project) -> Path:
    """Assemble a complete video from project components.

    Args:
        project: The project to assemble

    Returns:
        Path to the assembled video
    """
    # Load voiceover
    if not project.voiceover_path.exists():
        raise FileNotFoundError(f"Voiceover not found: {project.voiceover_path}")

    voiceover = AudioFileClip(str(project.voiceover_path))
    total_duration = voiceover.duration

    # Build video from footage clips
    video = _build_video_track(project, total_duration)

    # Add captions
    script = project.get_script() or ""
    word_timestamps = generate_word_timestamps(script, total_duration)
    video = render_captions(video, word_timestamps)

    # Add hook text
    hook = project.state.hook_text
    if hook:
        video = render_hook_text(video, hook)

    # Add background music
    final_audio = _build_audio_track(voiceover, project, total_duration)

    # Combine video and audio
    final_video = video.set_audio(final_audio)

    # Set duration
    final_video = final_video.set_duration(total_duration)

    return final_video


def _build_video_track(project: Project, duration: float) -> CompositeVideoClip:
    """Build the video track from footage clips.

    Args:
        project: The project with footage
        duration: Total video duration

    Returns:
        Composited video clip
    """
    footage_clips = project.state.footage_clips
    video_settings = settings.video

    if not footage_clips:
        # Create a black background if no footage
        from moviepy.editor import ColorClip

        return ColorClip(
            size=(video_settings.width, video_settings.height),
            color=(0, 0, 0),
            duration=duration,
        )

    # Calculate how long each clip should play
    clip_duration = duration / len(footage_clips)
    timeline = []

    current_time = 0.0
    video_clips = []

    for i, footage in enumerate(footage_clips):
        clip_path = project.footage_dir / footage.filename

        if not clip_path.exists():
            continue

        try:
            clip = VideoFileClip(str(clip_path))

            # Resize to fit our dimensions (crop to fill)
            clip = _resize_and_crop(clip, video_settings.width, video_settings.height)

            # Set timing
            clip_end = min(current_time + clip_duration, duration)
            actual_duration = clip_end - current_time

            # Loop or trim clip to fit
            if clip.duration < actual_duration:
                # Loop the clip
                loops_needed = int(actual_duration / clip.duration) + 1
                clip = clip.loop(n=loops_needed)

            clip = clip.subclip(0, actual_duration)
            clip = clip.set_start(current_time)

            video_clips.append(clip)

            # Record timeline
            timeline.append(
                TimelineEntry(
                    clip_filename=footage.filename,
                    start=current_time,
                    end=clip_end,
                    keyword=footage.keyword,
                )
            )

            current_time = clip_end

        except Exception as e:
            print(f"Warning: Could not load clip {clip_path}: {e}")
            continue

    # Save timeline
    project.set_timeline(timeline)

    if not video_clips:
        from moviepy.editor import ColorClip

        return ColorClip(
            size=(video_settings.width, video_settings.height),
            color=(0, 0, 0),
            duration=duration,
        )

    # Composite all clips
    return CompositeVideoClip(video_clips, size=(video_settings.width, video_settings.height))


def _resize_and_crop(
    clip: VideoFileClip,
    target_width: int,
    target_height: int,
) -> VideoFileClip:
    """Resize and crop clip to fill target dimensions."""
    # Calculate scale to fill (cover, not contain)
    scale_w = target_width / clip.w
    scale_h = target_height / clip.h
    scale = max(scale_w, scale_h)

    # Resize
    new_width = int(clip.w * scale)
    new_height = int(clip.h * scale)
    clip = clip.resize((new_width, new_height))

    # Crop to center
    x_center = new_width // 2
    y_center = new_height // 2
    x1 = x_center - target_width // 2
    y1 = y_center - target_height // 2

    clip = clip.crop(x1=x1, y1=y1, width=target_width, height=target_height)

    return clip


def _build_audio_track(
    voiceover: AudioFileClip,
    project: Project,
    duration: float,
) -> CompositeAudioClip:
    """Build the audio track with voiceover and music.

    Args:
        voiceover: The voiceover audio clip
        project: The project (for music selection)
        duration: Total duration

    Returns:
        Composited audio clip
    """
    music_settings = settings.music
    audio_clips = [voiceover]

    if music_settings.enabled:
        music_path = _get_music_track(project)

        if music_path and music_path.exists():
            try:
                music = AudioFileClip(str(music_path))

                # Loop music if needed
                if music.duration < duration:
                    loops = int(duration / music.duration) + 1
                    music = music.loop(n=loops)

                music = music.subclip(0, duration)

                # Apply volume and fades
                music = music.volumex(music_settings.volume)

                if music_settings.fade_in > 0:
                    music = music.audio_fadein(music_settings.fade_in)
                if music_settings.fade_out > 0:
                    music = music.audio_fadeout(music_settings.fade_out)

                audio_clips.append(music)

            except Exception as e:
                print(f"Warning: Could not load music: {e}")

    return CompositeAudioClip(audio_clips)


def _get_music_track(project: Project) -> Optional[Path]:
    """Get the music track for the project.

    Args:
        project: The project

    Returns:
        Path to music file or None
    """
    # Check if project has a specific track set
    if project.state.music_track:
        track_path = Path(project.state.music_track)
        if track_path.exists():
            return track_path

    # Get music by mood
    mood = project.state.music_mood or "calm"
    music_dir = get_assets_dir() / "music" / mood

    if not music_dir.exists():
        # Try any music folder
        music_base = get_assets_dir() / "music"
        if music_base.exists():
            for mood_dir in music_base.iterdir():
                if mood_dir.is_dir():
                    music_dir = mood_dir
                    break

    if not music_dir.exists():
        return None

    # Find music files
    music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))

    if not music_files:
        return None

    # Pick a random track
    return random.choice(music_files)


def render_preview(project: Project) -> Path:
    """Render a preview video (lower quality for speed).

    Args:
        project: The project to render

    Returns:
        Path to preview video
    """
    final_video = assemble_video(project)

    output_path = project.preview_path

    # Render at lower quality for preview
    final_video.write_videofile(
        str(output_path),
        fps=settings.video.fps,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=4,
    )

    # Clean up
    final_video.close()

    return output_path


def render_final(project: Project) -> Path:
    """Render the final high-quality video.

    Args:
        project: The project to render

    Returns:
        Path to final video
    """
    final_video = assemble_video(project)

    output_path = project.final_path

    # Render at high quality
    final_video.write_videofile(
        str(output_path),
        fps=settings.video.fps,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="medium",
        threads=4,
    )

    # Clean up
    final_video.close()

    return output_path
