"""Generate and render animated captions."""

import json
import re
from pathlib import Path
from typing import Optional

from moviepy import (
    CompositeVideoClip,
    TextClip,
)
from moviepy.video.fx import CrossFadeIn, CrossFadeOut

from ..core.config import settings


def load_word_timestamps(voiceover_path: Path) -> list[dict]:
    """Load word timestamps from ElevenLabs JSON file.

    Args:
        voiceover_path: Path to the voiceover audio file

    Returns:
        List of word timestamp dicts with 'word', 'start', 'end' keys
    """
    timestamps_path = voiceover_path.with_suffix(".timestamps.json")
    if timestamps_path.exists():
        with open(timestamps_path) as f:
            return json.load(f)
    return []


def generate_word_timestamps(
    script: str,
    audio_duration: float,
) -> list[dict]:
    """Generate timestamps for each word in the script (fallback method).

    This is only used when real timestamps from ElevenLabs are not available.

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

    # Use linear timing - equal time per word
    time_per_word = audio_duration / len(words)

    timestamps = []
    current_time = 0.0

    for word in words:
        timestamps.append(
            {
                "word": word,
                "start": current_time,
                "end": current_time + time_per_word,
            }
        )
        current_time += time_per_word

    return timestamps


def _clean_and_split(text: str) -> list[str]:
    """Clean text and split into words."""
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Split on whitespace
    words = text.split()

    # Filter empty strings
    return [w for w in words if w]


def _estimate_text_width(text: str, font_size: int) -> int:
    """Estimate the pixel width of text.

    This is a rough estimate based on average character width.
    Bold fonts are typically ~0.5-0.6 * font_size per character.
    """
    # Conservative estimate - bold fonts are wider
    char_width = font_size * 0.6
    return int(len(text) * char_width)


def _wrap_text_by_words(text: str, font_size: int, max_width: int) -> str:
    """Wrap text at word boundaries to fit within max_width.

    This prevents mid-word breaks that can happen with auto-wrapping.
    """
    words = text.split()
    if not words:
        return text

    lines = []
    current_line = []
    current_width = 0
    space_width = _estimate_text_width(" ", font_size)

    for word in words:
        word_width = _estimate_text_width(word, font_size)

        # Check if adding this word would exceed max_width
        if current_line:
            # Account for space between words
            new_width = current_width + space_width + word_width
        else:
            new_width = word_width

        if new_width <= max_width or not current_line:
            # Add word to current line (always add at least one word per line)
            current_line.append(word)
            current_width = new_width
        else:
            # Start a new line
            lines.append(" ".join(current_line))
            current_line = [word]
            current_width = word_width

    # Add the last line
    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)


def _preprocess_timestamps(word_timestamps: list[dict]) -> list[dict]:
    """Preprocess timestamps to split words that span paragraph breaks.

    ElevenLabs sometimes combines words across newlines like "customers.\n\nFinally,"
    which causes caption grouping issues. This splits them into separate entries.
    """
    processed = []

    for ts in word_timestamps:
        word = ts["word"]
        start = ts["start"]
        end = ts["end"]
        duration = end - start

        # Check if word contains paragraph breaks
        if "\n\n" in word:
            # Split on paragraph breaks
            parts = [p.strip() for p in word.split("\n\n") if p.strip()]
            if len(parts) > 1:
                # Distribute time proportionally by character count
                total_chars = sum(len(p) for p in parts)
                current_time = start

                for part in parts:
                    part_duration = duration * (len(part) / total_chars) if total_chars > 0 else duration / len(parts)
                    processed.append({
                        "word": part,
                        "start": current_time,
                        "end": current_time + part_duration,
                    })
                    current_time += part_duration
                continue

        # Check if word contains sentence-ending punctuation followed by more text
        # e.g., "word.Another" should be split
        match = re.match(r'^(.+[.!?])([A-Z].*)$', word)
        if match:
            part1, part2 = match.groups()
            total_chars = len(part1) + len(part2)
            part1_duration = duration * (len(part1) / total_chars)

            processed.append({
                "word": part1,
                "start": start,
                "end": start + part1_duration,
            })
            processed.append({
                "word": part2,
                "start": start + part1_duration,
                "end": end,
            })
            continue

        # Clean any remaining newlines from the word
        clean_word = word.replace("\n", " ").strip()
        if clean_word:
            processed.append({
                "word": clean_word,
                "start": start,
                "end": end,
            })

    return processed


def render_captions(
    video_clip,
    word_timestamps: list[dict],
    style: Optional[str] = None,
) -> CompositeVideoClip:
    """Render captions onto a video.

    Args:
        video_clip: The base video clip
        word_timestamps: List of word timing dicts (from ElevenLabs or generated)
        style: Caption style ('word_by_word', 'sentence')

    Returns:
        CompositeVideoClip with captions
    """
    style = style or settings.captions.style
    caption_settings = settings.captions

    if not caption_settings.enabled or not word_timestamps:
        return video_clip

    # Preprocess timestamps to split words that span paragraph breaks
    word_timestamps = _preprocess_timestamps(word_timestamps)

    if style == "word_by_word":
        return _render_word_by_word(video_clip, word_timestamps, caption_settings)
    else:
        return _render_sentence(video_clip, word_timestamps, caption_settings)


def _render_word_by_word(
    video_clip,
    word_timestamps: list[dict],
    caption_settings,
) -> CompositeVideoClip:
    """Render word-by-word animated captions."""
    text_clips = []

    font_size = caption_settings.font_size
    stroke_width = caption_settings.stroke_width

    # Add padding around text to prevent stroke clipping
    # Using "caption" method with fixed size gives us control over the text box
    text_height = int(font_size * 1.6 + stroke_width * 8)

    for ts in word_timestamps:
        word = ts["word"]
        start = ts["start"]
        end = ts["end"]
        duration = end - start

        if duration <= 0:
            continue

        try:
            txt_clip = TextClip(
                text=word,
                font_size=font_size,
                color=caption_settings.color,
                font=caption_settings.font,
                stroke_color=caption_settings.stroke_color,
                stroke_width=stroke_width,
                method="caption",
                size=(video_clip.w - 100, text_height),  # Fixed height with stroke padding
                text_align="center",
                duration=duration,
            )
            txt_clip = txt_clip.with_position(("center", "center"))
            txt_clip = txt_clip.with_start(start)
            text_clips.append(txt_clip)
        except Exception:
            continue

    return CompositeVideoClip([video_clip] + text_clips)


def _render_sentence(
    video_clip,
    word_timestamps: list[dict],
    caption_settings,
) -> CompositeVideoClip:
    """Render sentence-based captions with proper timing."""
    # Group words into sentences/chunks
    sentences = _group_into_sentences(word_timestamps)
    text_clips = []

    font_size = caption_settings.font_size
    stroke_width = caption_settings.stroke_width

    # Calculate text box dimensions with VERY generous padding
    # Leave plenty of room on sides to prevent any clipping
    horizontal_margin = 300  # Total margin (150px each side)
    text_width = video_clip.w - horizontal_margin

    # Allow for up to 4 lines of text plus generous padding for stroke
    line_height = int(font_size * 1.5)  # Generous line height for descenders
    text_height = line_height * 4 + stroke_width * 12  # Extra padding for stroke

    for sentence in sentences:
        words = [ts["word"] for ts in sentence]
        text = " ".join(words)
        start = sentence[0]["start"]
        end = sentence[-1]["end"]
        duration = end - start

        if duration <= 0:
            continue

        try:
            # Manually wrap text at word boundaries to prevent mid-word breaks
            # Use a smaller effective width for wrapping to ensure text fits with stroke
            wrap_width = text_width - stroke_width * 6
            wrapped_text = _wrap_text_by_words(text, font_size, wrap_width)

            txt_clip = TextClip(
                text=wrapped_text,
                font_size=font_size,
                color=caption_settings.color,
                font=caption_settings.font,
                stroke_color=caption_settings.stroke_color,
                stroke_width=stroke_width,
                method="caption",  # Use caption with size for stroke padding
                size=(text_width, text_height),  # Fixed size includes stroke padding
                text_align="center",
                duration=duration,
            )
            txt_clip = txt_clip.with_position(("center", "center"))
            txt_clip = txt_clip.with_start(start)
            text_clips.append(txt_clip)
        except Exception:
            continue

    return CompositeVideoClip([video_clip] + text_clips)


def _group_into_sentences(word_timestamps: list[dict], max_words: int = 4) -> list[list[dict]]:
    """Group words into sentence-like chunks for display.

    Args:
        word_timestamps: List of word timing dicts
        max_words: Maximum words per caption chunk (lower = faster pacing)

    Returns:
        List of sentence groups, each containing word timestamp dicts
    """
    sentences = []
    current_sentence = []

    for ts in word_timestamps:
        current_sentence.append(ts)
        word = ts["word"]

        # End sentence on punctuation or max words
        if word.endswith((".", "!", "?")) or len(current_sentence) >= max_words:
            sentences.append(current_sentence)
            current_sentence = []

    # Add remaining words
    if current_sentence:
        sentences.append(current_sentence)

    return sentences


def render_hook_text(
    video_clip,
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
        pos = ("center", "center")
    else:
        pos = ("center", int(video_clip.h * 0.2))

    try:
        hook_clip = TextClip(
            text=hook_text,
            font_size=hook_settings.font_size,
            color="#FFFFFF",
            font="arialbd.ttf",
            stroke_color="#000000",
            stroke_width=4,
            method="caption",
            size=(video_clip.w - 150, None),
            text_align="center",
            duration=duration,
        )
        hook_clip = hook_clip.with_position(pos)
        hook_clip = hook_clip.with_start(0)

        # Add fade effects
        hook_clip = hook_clip.with_effects([
            CrossFadeIn(0.3),
            CrossFadeOut(0.3),
        ])

        return CompositeVideoClip([video_clip, hook_clip])
    except Exception:
        return video_clip
