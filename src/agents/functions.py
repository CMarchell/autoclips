"""Agent-callable functions for AutoClips.

These functions are designed to be called by Claude Code or other AI agents
to create, modify, and manage video projects.
"""

from pathlib import Path
from typing import Any, Optional

from ..core.config import get_niche_config, get_voice_config
from ..core.database import get_db
from ..core.project import FootageClip, Project, ProjectStatus
from ..generators import generate_metadata, generate_script, generate_video_ideas, generate_voiceover
from ..media import download_clip, get_footage_for_script
from ..media.assembler import render_final, render_preview as _render_preview


# ============================================================================
# Discovery & Creation
# ============================================================================


def create_video(
    topic: str,
    niche: Optional[str] = None,
    voice_key: Optional[str] = None,
    auto_generate: bool = True,
) -> dict[str, Any]:
    """Create a new video project.

    This creates a project, generates script, fetches footage, generates voiceover,
    and leaves it ready for review.

    Args:
        topic: The video topic (e.g., "5 budgeting tips for beginners")
        niche: Optional niche for style customization (e.g., "finance")
        voice_key: Optional voice key from voices.yaml (e.g., "adam")
        auto_generate: If True, automatically generate all components

    Returns:
        Dict with project info and status
    """
    # Create project
    project = Project.create(topic, niche)

    db = get_db()
    db.create_project(project.id, topic, niche)

    result = {
        "project_id": project.id,
        "topic": topic,
        "niche": niche,
        "status": "created",
        "steps_completed": [],
    }

    if not auto_generate:
        return result

    try:
        # Generate script
        script_result = generate_script(topic, niche)
        project.set_script(script_result["script"])
        project._state.hook_text = script_result["hook"]
        project.save_state()
        result["steps_completed"].append("script")

        # Set voice
        if voice_key:
            voice_config = get_voice_config(voice_key)
            project.set_voice(voice_config.get("voice_id", ""), voice_key)
        else:
            # Use niche default
            niche_config = get_niche_config(niche)
            default_voice_key = niche_config.get("voice", {}).get("voice_key", "sam")
            voice_config = get_voice_config(default_voice_key)
            project.set_voice(voice_config.get("voice_id", ""), default_voice_key)

        # Get music mood from niche
        niche_config = get_niche_config(niche)
        music_mood = niche_config.get("music_mood", "calm")
        project.set_music("", music_mood)

        # Generate voiceover
        voice_result = generate_voiceover(
            script_result["script"],
            project.voiceover_path,
            voice_key=voice_key or niche_config.get("voice", {}).get("voice_key"),
            niche=niche,
        )
        result["steps_completed"].append("voiceover")
        result["duration"] = voice_result["duration"]

        # Fetch footage
        from ..core.config import settings
        clips_needed = settings.video.clips_per_video
        footage_list = get_footage_for_script(script_result["script"], niche, clips_needed=clips_needed)

        for i, footage in enumerate(footage_list):
            filename = f"{i + 1:03d}_{footage['matched_keyword'].replace(' ', '-')[:20]}.mp4"
            clip_path = download_clip(footage, project.footage_dir, filename)

            clip = FootageClip(
                filename=filename,
                pexels_id=footage["pexels_id"],
                keyword=footage["matched_keyword"],
                duration=footage["duration"],
                url=footage["url"],
            )
            project.add_footage(clip)

            # Track in database
            db.add_footage_usage(
                project.id,
                footage["pexels_id"],
                footage["matched_keyword"],
                filename,
            )

        result["steps_completed"].append("footage")
        result["footage_count"] = len(footage_list)

        # Generate metadata
        metadata = generate_metadata(topic, script_result["script"], niche)
        project.set_metadata(metadata)
        result["steps_completed"].append("metadata")

        # Update status
        project.set_status(ProjectStatus.DRAFT)
        db.update_project(project.id, status="draft", script=script_result["script"])
        db.add_topic_to_history(topic, niche)

        result["status"] = "draft"
        result["message"] = f"Video project created successfully. Run render_preview('{project.id}') to generate preview."

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def generate_ideas(
    niche: Optional[str] = None,
    count: int = 5,
) -> list[dict[str, str]]:
    """Generate video topic ideas.

    Args:
        niche: Niche to generate ideas for (e.g., "finance")
        count: Number of ideas to generate

    Returns:
        List of dicts with 'topic' and 'hook' keys
    """
    return generate_video_ideas(niche, count)


def list_projects(
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List all video projects.

    Args:
        status: Filter by status ("draft", "preview", "approved", "killed")

    Returns:
        List of project summaries
    """
    status_enum = None
    if status:
        status_enum = ProjectStatus(status)

    projects = Project.list_all(status_enum)
    return [p.get_summary() for p in projects]


# ============================================================================
# Inspection
# ============================================================================


def get_project_status(project_id: str) -> dict[str, Any]:
    """Get detailed status of a project.

    Args:
        project_id: The project ID

    Returns:
        Detailed project information
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    return project.get_summary()


def get_script(project_id: str) -> dict[str, Any]:
    """Get the script for a project.

    Args:
        project_id: The project ID

    Returns:
        Dict with script text and metadata
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    script = project.get_script()
    return {
        "project_id": project_id,
        "script": script,
        "word_count": project.state.word_count,
        "estimated_duration": project.state.duration,
        "hook": project.state.hook_text,
    }


def get_footage_list(project_id: str) -> dict[str, Any]:
    """Get the list of footage clips for a project.

    Args:
        project_id: The project ID

    Returns:
        Dict with footage list and details
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    footage = project.get_footage_list()
    return {
        "project_id": project_id,
        "footage_count": len(footage),
        "clips": footage,
    }


# ============================================================================
# Modifications
# ============================================================================


def update_script(project_id: str, new_script: str) -> dict[str, Any]:
    """Replace the entire script for a project.

    Args:
        project_id: The project ID
        new_script: The new script text

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    project.set_script(new_script)

    return {
        "project_id": project_id,
        "status": "updated",
        "word_count": project.state.word_count,
        "estimated_duration": project.state.duration,
        "message": "Script updated. Run regenerate_voiceover() to update audio.",
    }


def update_script_section(
    project_id: str,
    find: str,
    replace: str,
) -> dict[str, Any]:
    """Find and replace text in the script.

    Args:
        project_id: The project ID
        find: Text to find
        replace: Text to replace with

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    success = project.update_script_section(find, replace)

    if success:
        return {
            "project_id": project_id,
            "status": "updated",
            "message": "Script section updated. Run regenerate_voiceover() to update audio.",
        }
    else:
        return {
            "project_id": project_id,
            "status": "not_found",
            "message": f"Could not find text: '{find[:50]}...'",
        }


def remove_footage(
    project_id: str,
    clip_name_or_keyword: str,
) -> dict[str, Any]:
    """Remove a footage clip from the project.

    Args:
        project_id: The project ID
        clip_name_or_keyword: Filename or keyword to match

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    # Try as filename first
    success = project.remove_footage(filename=clip_name_or_keyword)

    # Try as keyword if filename didn't match
    if not success:
        success = project.remove_footage(keyword=clip_name_or_keyword)

    if success:
        return {
            "project_id": project_id,
            "status": "removed",
            "message": f"Removed footage matching '{clip_name_or_keyword}'",
            "remaining_clips": len(project.state.footage_clips),
        }
    else:
        return {
            "project_id": project_id,
            "status": "not_found",
            "message": f"No footage found matching '{clip_name_or_keyword}'",
        }


def replace_footage(
    project_id: str,
    clip_name_or_keyword: str,
    new_keyword: str,
) -> dict[str, Any]:
    """Replace a footage clip with a new one.

    Args:
        project_id: The project ID
        clip_name_or_keyword: Filename or keyword of clip to replace
        new_keyword: Keyword to search for replacement

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    # Find the clip to replace
    clip_to_replace = None
    clip_index = None
    for i, clip in enumerate(project.state.footage_clips):
        if clip.filename == clip_name_or_keyword or clip_name_or_keyword.lower() in clip.keyword.lower():
            clip_to_replace = clip
            clip_index = i
            break

    if not clip_to_replace:
        return {
            "project_id": project_id,
            "status": "not_found",
            "message": f"No footage found matching '{clip_name_or_keyword}'",
        }

    # Get IDs to exclude
    exclude_ids = [c.pexels_id for c in project.state.footage_clips]

    # Find replacement
    from ..media.footage import find_replacement_footage
    new_footage = find_replacement_footage(new_keyword, exclude_ids, project.state.niche)

    if not new_footage:
        return {
            "project_id": project_id,
            "status": "no_replacement",
            "message": f"Could not find replacement footage for '{new_keyword}'",
        }

    # Download new clip
    filename = f"{clip_index + 1:03d}_{new_keyword.replace(' ', '-')[:20]}.mp4"
    download_clip(new_footage, project.footage_dir, filename)

    # Remove old clip
    project.remove_footage(filename=clip_to_replace.filename)

    # Add new clip
    new_clip = FootageClip(
        filename=filename,
        pexels_id=new_footage["pexels_id"],
        keyword=new_keyword,
        duration=new_footage["duration"],
        url=new_footage["url"],
    )
    project.add_footage(new_clip)

    return {
        "project_id": project_id,
        "status": "replaced",
        "old_keyword": clip_to_replace.keyword,
        "new_keyword": new_keyword,
        "message": "Footage replaced successfully",
    }


def change_voice(
    project_id: str,
    voice_key: str,
) -> dict[str, Any]:
    """Change the voice for a project.

    Args:
        project_id: The project ID
        voice_key: Voice key from voices.yaml

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    voice_config = get_voice_config(voice_key)
    if not voice_config:
        return {"error": f"Unknown voice: {voice_key}"}

    project.set_voice(voice_config.get("voice_id", ""), voice_key)

    return {
        "project_id": project_id,
        "status": "updated",
        "voice": voice_key,
        "message": "Voice updated. Run regenerate_voiceover() to apply.",
    }


def change_music(
    project_id: str,
    mood_or_track: str,
) -> dict[str, Any]:
    """Change the background music for a project.

    Args:
        project_id: The project ID
        mood_or_track: Mood name ("energetic", "calm", "dramatic") or path to track

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    # Check if it's a mood or a path
    if mood_or_track in ["energetic", "calm", "dramatic"]:
        project.set_music("", mood_or_track)
    else:
        project.set_music(mood_or_track, None)

    return {
        "project_id": project_id,
        "status": "updated",
        "music": mood_or_track,
        "message": "Music updated. Re-render preview to apply.",
    }


def regenerate_voiceover(project_id: str) -> dict[str, Any]:
    """Regenerate the voiceover after script changes.

    Args:
        project_id: The project ID

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    script = project.get_script()
    if not script:
        return {"error": "No script found for project"}

    # Get voice settings
    voice_key = project.state.voice_name

    # Generate new voiceover
    result = generate_voiceover(
        script,
        project.voiceover_path,
        voice_key=voice_key,
        niche=project.state.niche,
    )

    return {
        "project_id": project_id,
        "status": "regenerated",
        "duration": result["duration"],
        "message": "Voiceover regenerated. Re-render preview to see changes.",
    }


# ============================================================================
# Pipeline Control
# ============================================================================


def render_preview(project_id: str) -> dict[str, Any]:
    """Render a preview video for review.

    Args:
        project_id: The project ID

    Returns:
        Status dict with preview path
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    try:
        preview_path = _render_preview(project)
        project.set_status(ProjectStatus.PREVIEW)

        db = get_db()
        db.update_project(project_id, status="preview")

        return {
            "project_id": project_id,
            "status": "preview_ready",
            "preview_path": str(preview_path),
            "message": "Preview rendered. Review and run approve_video() when ready.",
        }
    except Exception as e:
        return {
            "project_id": project_id,
            "status": "error",
            "error": str(e),
        }


def approve_video(project_id: str) -> dict[str, Any]:
    """Approve a video and render the final version.

    Args:
        project_id: The project ID

    Returns:
        Status dict with final video path
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    try:
        # Render final version
        final_path = render_final(project)

        # Move to output and mark approved
        output_path = project.approve()

        db = get_db()
        db.update_project(project_id, status="approved")

        return {
            "project_id": project_id,
            "status": "approved",
            "final_path": str(output_path),
            "message": "Video approved and ready for upload!",
        }
    except Exception as e:
        return {
            "project_id": project_id,
            "status": "error",
            "error": str(e),
        }


def kill_video(project_id: str, delete_files: bool = False) -> dict[str, Any]:
    """Kill a video project.

    Args:
        project_id: The project ID
        delete_files: If True, permanently delete all files

    Returns:
        Status dict
    """
    project = Project.load(project_id)
    if not project:
        return {"error": f"Project not found: {project_id}"}

    if delete_files:
        project.delete()
        db = get_db()
        db.delete_project(project_id)
        return {
            "project_id": project_id,
            "status": "deleted",
            "message": "Project permanently deleted.",
        }
    else:
        project.kill()
        db = get_db()
        db.update_project(project_id, status="killed")
        return {
            "project_id": project_id,
            "status": "killed",
            "message": "Project marked as killed. Use delete_files=True to permanently delete.",
        }
