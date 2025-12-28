"""Generate and render animated captions."""

import re
from pathlib import Path
from typing import Optional

from moviepy.editor import (
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
)

from ..core.config import settings


def generate_word_timestamps(
    script: str,
    audio_duration: float,
) -> list[dict]:
    """Generate timestamps for each word in the script.

    Args:
        script: The video script
        audio_duration: Duration of the audio in seconds

    Returns:
        List of dicts with 'word', 'start', 'end' keys
    """
    # Clean and split script into words
    words = _clean_and_split(script)

    if not words:
        return []

    # Calculate timing based on word length and audio duration
    # Weight longer words slightly more
    total_weight = sum(max(len(w), 1) ** 0.5 for w in words)
    time_per_weight = audio_duration / total_weight

    timestamps = []
    current_time = 0.0

    for word in words:
        word_weight = max(len(word), 1) ** 0.5
        word_duration = word_weight * time_per_weight

        # Minimum duration per word
        word_duration = max(word_duration, 0.15)

        timestamps.append(
            {
                "word": word,
                "start": current_time,
                "end": current_time + word_duration,
            }
        )

        current_time += word_duration

    # Normalize to fit exact audio duration
    if timestamps:
        scale = audio_duration / timestamps[-1]["end"]
        for ts in timestamps:
            ts["start"] *= scale
            ts["end"] *= scale

    return timestamps


def _clean_and_split(text: str) -> list[str]:
    """Clean text and split into words."""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Split on whitespace
    words = text.split()

    # Filter empty strings
    return [w for w in words if w]


def render_captions(
    video_clip: VideoFileClip,
    word_timestamps: list[dict],
    style: Optional[str] = None,
) -> CompositeVideoClip:
    """Render word-by-word captions onto a video.

    Args:
        video_clip: The base video clip
        word_timestamps: List of word timing dicts
        style: Caption style ('word_by_word', 'sentence')

    Returns:
        CompositeVideoClip with captions
    """
    style = style or settings.captions.style
    caption_settings = settings.captions

    if not caption_settings.enabled or not word_timestamps:
        return video_clip

    if style == "word_by_word":
        return _render_word_by_word(video_clip, word_timestamps, caption_settings)
    else:
        return _render_sentence(video_clip, word_timestamps, caption_settings)


def _render_word_by_word(
    video_clip: VideoFileClip,
    word_timestamps: list[dict],
    caption_settings,
) -> CompositeVideoClip:
    """Render word-by-word animated captions."""
    text_clips = []

    # Calculate position
    if caption_settings.position == "center":
        pos_y = video_clip.h // 2
    elif caption_settings.position == "bottom":
        pos_y = int(video_clip.h * 0.75)
    else:
        pos_y = int(video_clip.h * 0.5)

    for ts in word_timestamps:
        word = ts["word"]
        start = ts["start"]
        end = ts["end"]
        duration = end - start

        # Create text clip
        try:
            txt_clip = (
                TextClip(
                    word,
                    fontsize=caption_settings.font_size,
                    color=caption_settings.color,
                    font=caption_settings.font,
                    stroke_color=caption_settings.stroke_color,
                    stroke_width=caption_settings.stroke_width,
                    method="caption",
                    size=(video_clip.w - 100, None),
                    align="center",
                )
                .set_position(("center", pos_y))
                .set_start(start)
                .set_duration(duration)
            )
            text_clips.append(txt_clip)
        except Exception:
            # Skip problematic words
            continue

    return CompositeVideoClip([video_clip] + text_clips)


def _render_sentence(
    video_clip: VideoFileClip,
    word_timestamps: list[dict],
    caption_settings,
) -> CompositeVideoClip:
    """Render sentence-based captions."""
    # Group words into sentences/chunks
    sentences = _group_into_sentences(word_timestamps)
    text_clips = []

    # Calculate position
    if caption_settings.position == "center":
        pos_y = video_clip.h // 2
    elif caption_settings.position == "bottom":
        pos_y = int(video_clip.h * 0.75)
    else:
        pos_y = int(video_clip.h * 0.5)

    for sentence in sentences:
        words = [ts["word"] for ts in sentence]
        text = " ".join(words)
        start = sentence[0]["start"]
        end = sentence[-1]["end"]
        duration = end - start

        try:
            txt_clip = (
                TextClip(
                    text,
                    fontsize=int(caption_settings.font_size * 0.7),  # Smaller for sentences
                    color=caption_settings.color,
                    font=caption_settings.font,
                    stroke_color=caption_settings.stroke_color,
                    stroke_width=caption_settings.stroke_width,
                    method="caption",
                    size=(video_clip.w - 80, None),
                    align="center",
                )
                .set_position(("center", pos_y))
                .set_start(start)
                .set_duration(duration)
            )
            text_clips.append(txt_clip)
        except Exception:
            continue

    return CompositeVideoClip([video_clip] + text_clips)


def _group_into_sentences(word_timestamps: list[dict], max_words: int = 8) -> list[list[dict]]:
    """Group words into sentence-like chunks."""
    sentences = []
    current_sentence = []

    for ts in word_timestamps:
        current_sentence.append(ts)
        word = ts["word"]

        # End sentence on punctuation or max words
        if (
            word.endswith((".", "!", "?", ","))
            or len(current_sentence) >= max_words
        ):
            sentences.append(current_sentence)
            current_sentence = []

    # Add remaining words
    if current_sentence:
        sentences.append(current_sentence)

    return sentences


def render_hook_text(
    video_clip: VideoFileClip,
    hook_text: str,
    duration: Optional[float] = None,
) -> CompositeVideoClip:
    """Render hook text overlay at the start of video.

    Args:
        video_clip: The base video clip
        hook_text: The hook text to display
        duration: How long to show the hook (default from settings)

    Returns:
        CompositeVideoClip with hook text
    """
    hook_settings = settings.hook_text

    if not hook_settings.enabled or not hook_text:
        return video_clip

    duration = duration or hook_settings.duration

    # Calculate position
    if hook_settings.position == "top_center":
        pos = ("center", int(video_clip.h * 0.15))
    elif hook_settings.position == "center":
        pos = ("center", video_clip.h // 2)
    else:
        pos = ("center", int(video_clip.h * 0.2))

    try:
        hook_clip = (
            TextClip(
                hook_text,
                fontsize=hook_settings.font_size,
                color="#FFFFFF",
                font="Arial-Bold",
                stroke_color="#000000",
                stroke_width=4,
                method="caption",
                size=(video_clip.w - 100, None),
                align="center",
            )
            .set_position(pos)
            .set_start(0)
            .set_duration(duration)
            .crossfadein(0.3)
            .crossfadeout(0.3)
        )

        return CompositeVideoClip([video_clip, hook_clip])
    except Exception:
        return video_clip
