"""Generate video scripts using AI."""

from typing import Optional

from ..core.config import get_niche_config, settings
from .llm import call_llm


def generate_script(
    topic: str,
    niche: Optional[str] = None,
    duration_target: Optional[int] = None,
) -> dict[str, any]:
    """Generate a video script for a topic.

    Args:
        topic: The video topic
        niche: Niche for style customization
        duration_target: Target duration in seconds (default from settings)

    Returns:
        Dict with 'script', 'hook', 'word_count', 'estimated_duration'
    """
    niche_config = get_niche_config(niche)
    prompts = niche_config.get("prompts", {})

    # Calculate target word count
    if duration_target is None:
        duration_target = (settings.video.duration_min + settings.video.duration_max) // 2

    # Assume ~2.5 words per second speaking pace
    word_count_target = int(duration_target * 2.5)

    # Build the prompt
    system_prompt = prompts.get("system", _get_default_system_prompt())
    script_template = prompts.get("script_prompt", _get_default_script_prompt())

    user_prompt = script_template.format(
        topic=topic,
        duration_target=duration_target,
        word_count=word_count_target,
    )

    # Generate the script
    script = call_llm(
        user_prompt,
        system_prompt=system_prompt,
        temperature=settings.ai.temperature,
    )

    # Clean up the script
    script = _clean_script(script)

    # Extract hook (first sentence or line)
    hook = extract_hook(script)

    # Calculate actual stats
    actual_word_count = len(script.split())
    estimated_duration = actual_word_count / 2.5

    return {
        "script": script,
        "hook": hook,
        "word_count": actual_word_count,
        "estimated_duration": estimated_duration,
    }


def extract_hook(script: str) -> str:
    """Extract the hook (first sentence) from a script.

    Args:
        script: The full script

    Returns:
        The hook text
    """
    if not script:
        return ""

    # Try to get first sentence
    for end_char in [".", "!", "?"]:
        if end_char in script:
            idx = script.index(end_char)
            # Don't cut too short
            if idx > 10:
                return script[: idx + 1].strip()

    # Fallback: first line or first N words
    first_line = script.split("\n")[0].strip()
    if len(first_line) > 10:
        return first_line[:100]

    # Last resort: first 10 words
    words = script.split()[:10]
    return " ".join(words)


def refine_script(
    script: str,
    instruction: str,
    niche: Optional[str] = None,
) -> str:
    """Refine an existing script based on instructions.

    Args:
        script: The current script
        instruction: What to change (e.g., "make it more energetic")
        niche: Niche for style context

    Returns:
        The refined script
    """
    niche_config = get_niche_config(niche)
    style = niche_config.get("prompts", {}).get("style", "conversational")

    prompt = f"""Here is a short-form video script:

---
{script}
---

Please refine this script based on the following instruction:
{instruction}

Maintain the {style} style. Keep the length similar.
Return ONLY the refined script, no explanations or labels."""

    refined = call_llm(prompt, temperature=0.7)
    return _clean_script(refined)


def _clean_script(script: str) -> str:
    """Clean up a generated script."""
    # Remove common artifacts
    script = script.strip()

    # Remove markdown code blocks if present
    if script.startswith("```"):
        script = script.split("\n", 1)[1] if "\n" in script else script[3:]
    if script.endswith("```"):
        script = script.rsplit("```", 1)[0]

    # Remove quotes if the whole thing is quoted
    if script.startswith('"') and script.endswith('"'):
        script = script[1:-1]
    if script.startswith("'") and script.endswith("'"):
        script = script[1:-1]

    # Remove stage directions like [pause], (beat), etc.
    import re

    script = re.sub(r"\[.*?\]", "", script)
    script = re.sub(r"\(.*?\)", "", script)

    # Clean up extra whitespace
    script = re.sub(r"\n{3,}", "\n\n", script)
    script = re.sub(r"  +", " ", script)

    return script.strip()


def _get_default_system_prompt() -> str:
    """Get the default system prompt for script generation."""
    return """You are a skilled short-form video scriptwriter. Your scripts are:
- Engaging and hook-driven (start with something attention-grabbing)
- Conversational and natural (written for speaking, not reading)
- Concise and punchy (30-70 seconds when read aloud)
- Actionable or thought-provoking (give value or spark curiosity)

Structure your scripts with:
1. A hook (first 3 seconds must grab attention)
2. The main content (2-4 key points maximum)
3. A call-to-action or memorable closing

Do NOT include:
- Stage directions or speaker labels
- Timestamps or section headers
- Emojis or special characters
- "Subscribe" or platform-specific CTAs

Write ONLY the spoken words, nothing else."""


def _get_default_script_prompt() -> str:
    """Get the default script generation prompt."""
    return """Write a short-form video script about: {topic}

The script should be {duration_target} seconds when read at a natural pace
(approximately {word_count} words).

Make it engaging, valuable, and memorable."""
