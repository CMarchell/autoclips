"""Generate video metadata (titles, descriptions, tags) using AI."""

from typing import Optional

from ..core.config import get_niche_config
from ..core.project import ProjectMetadata
from .llm import call_llm


def generate_metadata(
    topic: str,
    script: str,
    niche: Optional[str] = None,
) -> ProjectMetadata:
    """Generate metadata for a video.

    Args:
        topic: The video topic
        script: The video script
        niche: Niche for style customization

    Returns:
        ProjectMetadata object
    """
    niche_config = get_niche_config(niche)
    metadata_config = niche_config.get("metadata", {})

    title_style = metadata_config.get("title_style", "curiosity")
    hashtag_count = metadata_config.get("hashtag_count", 8)
    default_hashtags = metadata_config.get("default_hashtags", [])

    prompt = f"""Generate metadata for a short-form video.

Topic: {topic}

Script:
---
{script}
---

Generate:
1. A compelling title (max 100 characters) that uses a {title_style} style
   - curiosity: Creates intrigue, makes people want to know more
   - direct: Clear, straightforward, tells exactly what they'll learn
   - question: Poses a question the video answers

2. A description (2-3 sentences) that:
   - Summarizes the value
   - Includes relevant keywords
   - Has a soft call-to-action

3. {hashtag_count} relevant hashtags (mix of popular and niche)

4. 5-8 SEO tags (keywords for searchability)

Format your response as JSON:
{{
  "title": "...",
  "description": "...",
  "hashtags": ["#tag1", "#tag2", ...],
  "tags": ["tag1", "tag2", ...]
}}

Return ONLY the JSON, no other text."""

    response = call_llm(prompt, temperature=0.7)

    # Parse JSON response
    try:
        import json

        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            response = response.rsplit("```", 1)[0]

        data = json.loads(response)

        # Merge default hashtags
        hashtags = data.get("hashtags", [])
        for tag in default_hashtags:
            if tag not in hashtags:
                hashtags.append(tag)

        return ProjectMetadata(
            title=data.get("title", topic),
            description=data.get("description", ""),
            hashtags=hashtags,
            tags=data.get("tags", []),
        )
    except (json.JSONDecodeError, KeyError):
        # Fallback metadata
        return ProjectMetadata(
            title=topic,
            description=f"Learn about {topic} in this quick video!",
            hashtags=default_hashtags or ["#shorts", "#viral"],
            tags=[topic],
        )


def generate_platform_metadata(
    base_metadata: ProjectMetadata,
    platform: str,
) -> dict[str, str]:
    """Generate platform-specific metadata.

    Args:
        base_metadata: The base metadata
        platform: Target platform (tiktok, youtube, instagram)

    Returns:
        Dict with platform-specific fields
    """
    if platform == "tiktok":
        # TikTok: caption with hashtags, limited length
        caption = base_metadata.title
        hashtag_str = " ".join(base_metadata.hashtags[:10])
        full_caption = f"{caption} {hashtag_str}"

        # TikTok caption limit is ~2200 chars, but shorter is better
        if len(full_caption) > 300:
            full_caption = full_caption[:297] + "..."

        return {
            "caption": full_caption,
            "hashtags": base_metadata.hashtags[:10],
        }

    elif platform == "youtube":
        # YouTube: title, description, tags
        return {
            "title": base_metadata.title[:100],  # YouTube title limit
            "description": f"{base_metadata.description}\n\n{' '.join(base_metadata.hashtags[:3])}",
            "tags": base_metadata.tags + [h.replace("#", "") for h in base_metadata.hashtags],
        }

    elif platform == "instagram":
        # Instagram: caption with hashtags
        hashtag_str = " ".join(base_metadata.hashtags[:30])  # IG allows 30 hashtags
        caption = f"{base_metadata.title}\n\n{base_metadata.description}\n\n{hashtag_str}"

        return {
            "caption": caption[:2200],  # IG caption limit
        }

    return {}


def update_metadata_field(
    metadata: ProjectMetadata,
    field: str,
    instruction: str,
) -> ProjectMetadata:
    """Update a specific metadata field based on instruction.

    Args:
        metadata: Current metadata
        field: Field to update (title, description, hashtags, tags)
        instruction: What to change

    Returns:
        Updated metadata
    """
    current_value = getattr(metadata, field, None)

    prompt = f"""Update this {field} based on the instruction.

Current {field}: {current_value}

Instruction: {instruction}

Return ONLY the new {field}, nothing else."""

    new_value = call_llm(prompt, temperature=0.7).strip()

    # Handle list fields
    if field in ["hashtags", "tags"]:
        import json

        try:
            if new_value.startswith("["):
                new_value = json.loads(new_value)
            else:
                # Parse comma or space separated
                new_value = [
                    v.strip() for v in new_value.replace(",", " ").split() if v.strip()
                ]
        except json.JSONDecodeError:
            new_value = [new_value]

    # Create updated metadata
    data = metadata.model_dump()
    data[field] = new_value
    return ProjectMetadata(**data)
