"""Generate video topic ideas using AI."""

from typing import Optional

from ..core.config import get_niche_config, settings
from ..core.database import get_db
from .llm import call_llm


def generate_video_ideas(
    niche: Optional[str] = None,
    count: int = 5,
    exclude_recent: bool = True,
) -> list[dict[str, str]]:
    """Generate video topic ideas for a niche.

    Args:
        niche: Niche to generate ideas for (e.g., 'finance')
        count: Number of ideas to generate
        exclude_recent: Whether to check against recently used topics

    Returns:
        List of dicts with 'topic' and 'hook' keys
    """
    niche_config = get_niche_config(niche)
    niche_name = niche_config.get("display_name", niche or "general content")

    # Get recent topics to avoid
    recent_topics = []
    if exclude_recent:
        db = get_db()
        recent = db.get_recent_topics(limit=30)
        recent_topics = [t.topic for t in recent]

    recent_topics_text = ""
    if recent_topics:
        recent_topics_text = f"""
Avoid these recently used topics:
{chr(10).join(f'- {t}' for t in recent_topics[:20])}
"""

    prompt = f"""Generate {count} unique, engaging video topic ideas for {niche_name} content.

Each topic should:
1. Be specific enough to create a 30-70 second video
2. Have a natural hook that grabs attention in the first 3 seconds
3. Provide clear value to viewers
4. Be different from generic, overused topics
{recent_topics_text}
Format your response as a JSON array with objects containing 'topic' and 'hook' keys:
[
  {{"topic": "The 50/30/20 budgeting rule explained", "hook": "You're probably budgeting wrong..."}},
  {{"topic": "Why you should never pay minimums on credit cards", "hook": "Banks don't want you to know this..."}}
]

Return ONLY the JSON array, no other text."""

    response = call_llm(prompt, temperature=0.9)

    # Parse the JSON response
    try:
        import json

        # Clean up response if needed
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            response = response.rsplit("```", 1)[0]

        ideas = json.loads(response)
        return ideas[:count]
    except (json.JSONDecodeError, IndexError):
        # Fallback: return raw topics
        return [{"topic": response, "hook": ""}]


def check_topic_uniqueness(topic: str) -> dict[str, any]:
    """Check if a topic is unique enough to use.

    Args:
        topic: Topic to check

    Returns:
        Dict with 'is_unique', 'similar_topics', and 'suggestion'
    """
    db = get_db()

    # Check exact/near match
    is_recent = db.is_topic_recently_used(topic)

    if is_recent:
        # Get similar topics for context
        recent = db.get_recent_topics(limit=10)
        similar = [t.topic for t in recent if topic.lower()[:20] in t.topic.lower()]

        return {
            "is_unique": False,
            "similar_topics": similar,
            "suggestion": "This topic was recently used. Consider a different angle or topic.",
        }

    return {
        "is_unique": True,
        "similar_topics": [],
        "suggestion": None,
    }
