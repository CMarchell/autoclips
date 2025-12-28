"""Fetch stock footage from Pexels API."""

import re
from pathlib import Path
from typing import Optional

import httpx

from ..core.config import get_niche_config, settings
from ..core.database import get_db
from ..generators.llm import call_llm


def search_footage(
    keyword: str,
    min_duration: Optional[int] = None,
    exclude_used: bool = True,
) -> list[dict]:
    """Search for footage on Pexels.

    Args:
        keyword: Search keyword
        min_duration: Minimum clip duration in seconds
        exclude_used: Whether to exclude recently used clips

    Returns:
        List of video metadata dicts
    """
    min_duration = min_duration or settings.pexels.min_duration

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": settings.pexels_api_key}
    params = {
        "query": keyword,
        "orientation": settings.pexels.orientation,
        "per_page": settings.pexels.per_page,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    videos = []
    db = get_db() if exclude_used else None

    for video in data.get("videos", []):
        # Filter by duration
        if video.get("duration", 0) < min_duration:
            continue

        # Check if recently used
        if db and db.is_footage_recently_used(video["id"]):
            continue

        # Find best quality portrait video file
        video_files = video.get("video_files", [])
        best_file = _select_best_video_file(video_files)

        if best_file:
            videos.append(
                {
                    "pexels_id": video["id"],
                    "keyword": keyword,
                    "duration": video["duration"],
                    "width": best_file.get("width", 0),
                    "height": best_file.get("height", 0),
                    "url": best_file["link"],
                    "preview_url": video.get("image", ""),
                }
            )

    return videos


def _select_best_video_file(video_files: list[dict]) -> Optional[dict]:
    """Select the best video file for our needs (portrait, HD)."""
    # Prefer portrait orientation, HD quality
    portrait_files = [
        f for f in video_files if f.get("height", 0) > f.get("width", 0)
    ]

    if not portrait_files:
        # Fall back to any file
        portrait_files = video_files

    if not portrait_files:
        return None

    # Sort by height (quality) descending, but cap at 1920
    sorted_files = sorted(
        portrait_files,
        key=lambda f: min(f.get("height", 0), 1920),
        reverse=True,
    )

    return sorted_files[0]


def download_clip(
    video_info: dict,
    output_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    """Download a video clip from Pexels.

    Args:
        video_info: Video metadata from search_footage
        output_dir: Directory to save the clip
        filename: Optional filename (default: generated from keyword)

    Returns:
        Path to downloaded file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        keyword_slug = re.sub(r"[^\w\s-]", "", video_info["keyword"])
        keyword_slug = re.sub(r"[-\s]+", "-", keyword_slug).strip("-")[:20]
        filename = f"{video_info['pexels_id']}_{keyword_slug}.mp4"

    output_path = output_dir / filename

    # Download the video
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.get(video_info["url"])
        response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(response.content)

    return output_path


def get_footage_for_script(
    script: str,
    niche: Optional[str] = None,
    clips_needed: int = 5,
) -> list[dict]:
    """Extract keywords from script and find matching footage.

    Args:
        script: The video script
        niche: Niche for keyword boosting
        clips_needed: Number of clips to find

    Returns:
        List of video metadata dicts with keywords
    """
    # Get keywords from script using AI
    keywords = _extract_keywords(script, niche, clips_needed)

    # Search for each keyword
    all_footage = []
    used_ids = set()

    for keyword in keywords:
        results = search_footage(keyword, exclude_used=True)

        for video in results:
            if video["pexels_id"] not in used_ids:
                video["matched_keyword"] = keyword
                all_footage.append(video)
                used_ids.add(video["pexels_id"])

                if len(all_footage) >= clips_needed:
                    break

        if len(all_footage) >= clips_needed:
            break

    # If not enough footage, try generic keywords
    if len(all_footage) < clips_needed:
        generic_keywords = ["abstract", "nature", "city", "technology", "people"]
        for keyword in generic_keywords:
            results = search_footage(keyword, exclude_used=True)
            for video in results:
                if video["pexels_id"] not in used_ids:
                    video["matched_keyword"] = keyword
                    all_footage.append(video)
                    used_ids.add(video["pexels_id"])

                    if len(all_footage) >= clips_needed:
                        break
            if len(all_footage) >= clips_needed:
                break

    return all_footage[:clips_needed]


def _extract_keywords(
    script: str,
    niche: Optional[str],
    count: int,
) -> list[str]:
    """Extract visual keywords from script using AI.

    Args:
        script: The video script
        niche: Niche for context
        count: Number of keywords to extract

    Returns:
        List of search keywords
    """
    # Get niche keyword boosts
    niche_config = get_niche_config(niche)
    boost_keywords = niche_config.get("footage_keywords_boost", [])

    boost_text = ""
    if boost_keywords:
        boost_text = f"\nPrefer these types of visuals when relevant: {', '.join(boost_keywords)}"

    prompt = f"""Extract {count + 2} visual keywords from this script for searching stock footage.

Script:
---
{script}
---

Requirements:
- Keywords should describe concrete, filmable scenes or objects
- Each keyword should be 1-3 words that would return good stock footage
- Vary the keywords to create visual variety
- Avoid abstract concepts that don't film well
{boost_text}

Return ONLY a JSON array of keywords, e.g.: ["keyword1", "keyword2", ...]"""

    response = call_llm(prompt, temperature=0.7)

    # Parse response
    try:
        import json

        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            response = response.rsplit("```", 1)[0]

        keywords = json.loads(response)
        return keywords[: count + 2]
    except (json.JSONDecodeError, IndexError):
        # Fallback: extract nouns from script
        words = script.lower().split()
        # Return unique words longer than 4 chars
        unique_words = list(dict.fromkeys(w for w in words if len(w) > 4))
        return unique_words[:count]


def find_replacement_footage(
    current_keyword: str,
    exclude_ids: list[int],
    niche: Optional[str] = None,
) -> Optional[dict]:
    """Find replacement footage for a clip.

    Args:
        current_keyword: The keyword to search for alternatives
        exclude_ids: Pexels IDs to exclude
        niche: Niche for keyword boosting

    Returns:
        Video metadata dict or None
    """
    # Try the same keyword first
    results = search_footage(current_keyword, exclude_used=True)
    for video in results:
        if video["pexels_id"] not in exclude_ids:
            return video

    # Try related keywords
    prompt = f"""Suggest 3 alternative search keywords for stock footage.
Current keyword: {current_keyword}

Return ONLY a JSON array, e.g.: ["alt1", "alt2", "alt3"]"""

    try:
        response = call_llm(prompt, temperature=0.8)
        import json

        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            response = response.rsplit("```", 1)[0]
        alternatives = json.loads(response)

        for alt_keyword in alternatives:
            results = search_footage(alt_keyword, exclude_used=True)
            for video in results:
                if video["pexels_id"] not in exclude_ids:
                    video["matched_keyword"] = alt_keyword
                    return video
    except (json.JSONDecodeError, Exception):
        pass

    return None
