from .functions import (
    # Discovery & Creation
    create_video,
    generate_ideas,
    list_projects,
    # Inspection
    get_project_status,
    get_script,
    get_footage_list,
    # Modifications
    update_script,
    update_script_section,
    remove_footage,
    replace_footage,
    change_voice,
    change_music,
    regenerate_voiceover,
    # Pipeline Control
    render_preview,
    approve_video,
    kill_video,
)

__all__ = [
    "create_video",
    "generate_ideas",
    "list_projects",
    "get_project_status",
    "get_script",
    "get_footage_list",
    "update_script",
    "update_script_section",
    "remove_footage",
    "replace_footage",
    "change_voice",
    "change_music",
    "regenerate_voiceover",
    "render_preview",
    "approve_video",
    "kill_video",
]
