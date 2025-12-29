"""AutoClips CLI - AI Short-Form Video Generator."""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .agents import (
    approve_video,
    create_video,
    generate_ideas,
    get_footage_list,
    get_project_status,
    get_script,
    kill_video,
    list_projects,
    regenerate_voiceover,
    remove_footage,
    render_preview,
    update_script,
)

app = typer.Typer(
    name="autoclips",
    help="AI-powered short-form video generation pipeline",
    add_completion=False,
)
console = Console()


@app.command()
def create(
    topic: str = typer.Argument(..., help="The video topic"),
    niche: Optional[str] = typer.Option(None, "--niche", "-n", help="Niche for style (e.g., finance)"),
    voice: Optional[str] = typer.Option(None, "--voice", "-v", help="Voice key from voices.yaml"),
    no_generate: bool = typer.Option(False, "--no-generate", help="Create project without generating content"),
):
    """Create a new video project."""
    console.print(f"[bold blue]Creating video:[/] {topic}")

    if niche:
        console.print(f"[dim]Niche: {niche}[/]")
    if voice:
        console.print(f"[dim]Voice: {voice}[/]")

    with console.status("[bold green]Generating video components..."):
        result = create_video(
            topic=topic,
            niche=niche,
            voice_key=voice,
            auto_generate=not no_generate,
        )

    if result.get("status") == "error":
        console.print(f"[red]Error: {result.get('error')}[/]")
        raise typer.Exit(1)

    console.print(f"\n[green]Project created: {result['project_id']}[/]")
    console.print(f"[dim]Steps completed: {', '.join(result.get('steps_completed', []))}[/]")

    if result.get("duration"):
        console.print(f"[dim]Duration: {result['duration']:.1f}s[/]")
    if result.get("footage_count"):
        console.print(f"[dim]Footage clips: {result['footage_count']}[/]")

    console.print(f"\n[yellow]Next: autoclips preview {result['project_id']}[/]")


@app.command()
def ideas(
    niche: Optional[str] = typer.Option(None, "--niche", "-n", help="Niche for ideas"),
    count: int = typer.Option(5, "--count", "-c", help="Number of ideas"),
):
    """Generate video topic ideas."""
    with console.status("[bold green]Generating ideas..."):
        ideas_list = generate_ideas(niche=niche, count=count)

    console.print(f"\n[bold]Video Ideas{f' ({niche})' if niche else ''}:[/]\n")

    for i, idea in enumerate(ideas_list, 1):
        console.print(f"[cyan]{i}.[/] {idea.get('topic', idea)}")
        if idea.get("hook"):
            console.print(f"   [dim]Hook: {idea['hook']}[/]")
        console.print()


@app.command("list")
def list_cmd(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """List all video projects."""
    projects = list_projects(status=status)

    if not projects:
        console.print("[yellow]No projects found.[/]")
        return

    table = Table(title="Video Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Topic", max_width=40)
    table.add_column("Status", style="green")
    table.add_column("Duration")
    table.add_column("Created")

    for p in projects:
        duration = f"{p.get('estimated_duration', 0):.0f}s" if p.get("estimated_duration") else "-"
        created = p.get("created_at", "")[:10]
        table.add_row(
            p["id"][:30] + "..." if len(p["id"]) > 30 else p["id"],
            p.get("topic", "")[:40],
            p.get("status", ""),
            duration,
            created,
        )

    console.print(table)


@app.command()
def status(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """Get detailed status of a project."""
    result = get_project_status(project_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Project: {result['id']}[/]\n")
    console.print(f"Topic: {result.get('topic', 'N/A')}")
    console.print(f"Niche: {result.get('niche', 'N/A')}")
    console.print(f"Status: [green]{result.get('status', 'N/A')}[/]")
    console.print(f"Duration: {result.get('estimated_duration', 0):.1f}s")
    console.print(f"Word count: {result.get('word_count', 0)}")
    console.print(f"Footage clips: {result.get('footage_count', 0)}")
    console.print(f"Voice: {result.get('voice', 'N/A')}")
    console.print(f"Music: {result.get('music', 'N/A')}")
    console.print(f"Has preview: {'Yes' if result.get('has_preview') else 'No'}")
    console.print(f"Has final: {'Yes' if result.get('has_final') else 'No'}")


@app.command()
def script(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """View the script for a project."""
    result = get_script(project_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Script for {project_id}[/]\n")
    console.print(f"[yellow]Hook:[/] {result.get('hook', 'N/A')}\n")
    console.print("[dim]─" * 50 + "[/]")
    console.print(result.get("script", "No script found"))
    console.print("[dim]─" * 50 + "[/]")
    console.print(f"\n[dim]Words: {result.get('word_count', 0)} | Duration: {result.get('estimated_duration', 0):.1f}s[/]")


@app.command()
def footage(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """View footage clips for a project."""
    result = get_footage_list(project_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Footage for {project_id}[/]\n")

    table = Table()
    table.add_column("#", style="cyan")
    table.add_column("Filename")
    table.add_column("Keyword")
    table.add_column("Duration")

    for i, clip in enumerate(result.get("clips", []), 1):
        table.add_row(
            str(i),
            clip.get("filename", ""),
            clip.get("keyword", ""),
            f"{clip.get('duration', 0):.1f}s",
        )

    console.print(table)


@app.command()
def preview(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """Render a preview video."""
    console.print(f"[bold blue]Rendering preview for {project_id}...[/]")

    with console.status("[bold green]Rendering..."):
        result = render_preview(project_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"\n[green][OK] Preview rendered![/]")
    console.print(f"[dim]Path: {result.get('preview_path')}[/]")
    console.print(f"\n[yellow]Next: autoclips approve {project_id}[/]")


@app.command()
def approve(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """Approve and render final video."""
    console.print(f"[bold blue]Approving {project_id}...[/]")

    with console.status("[bold green]Rendering final video..."):
        result = approve_video(project_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"\n[green][OK] Video approved and ready![/]")
    console.print(f"[dim]Path: {result.get('final_path')}[/]")


@app.command()
def kill(
    project_id: str = typer.Argument(..., help="Project ID"),
    delete: bool = typer.Option(False, "--delete", "-d", help="Permanently delete files"),
):
    """Kill a video project."""
    result = kill_video(project_id, delete_files=delete)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"[yellow][OK] {result.get('message')}[/]")


@app.command("update-script")
def update_script_cmd(
    project_id: str = typer.Argument(..., help="Project ID"),
    script_file: str = typer.Argument(..., help="Path to new script file"),
):
    """Update project script from a file."""
    try:
        with open(script_file) as f:
            new_script = f.read()
    except FileNotFoundError:
        console.print(f"[red]File not found: {script_file}[/]")
        raise typer.Exit(1)

    result = update_script(project_id, new_script)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"[green][OK] Script updated![/]")
    console.print(f"[dim]{result.get('message')}[/]")


@app.command("remove-footage")
def remove_footage_cmd(
    project_id: str = typer.Argument(..., help="Project ID"),
    keyword: str = typer.Argument(..., help="Filename or keyword to match"),
):
    """Remove footage from a project."""
    result = remove_footage(project_id, keyword)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    if result.get("status") == "removed":
        console.print(f"[green][OK] {result.get('message')}[/]")
    else:
        console.print(f"[yellow]{result.get('message')}[/]")


@app.command("regen-voice")
def regen_voice_cmd(
    project_id: str = typer.Argument(..., help="Project ID"),
):
    """Regenerate voiceover after script changes."""
    console.print(f"[bold blue]Regenerating voiceover...[/]")

    with console.status("[bold green]Generating..."):
        result = regenerate_voiceover(project_id)

    if result.get("error"):
        console.print(f"[red]Error: {result['error']}[/]")
        raise typer.Exit(1)

    console.print(f"[green][OK] Voiceover regenerated![/]")
    console.print(f"[dim]Duration: {result.get('duration', 0):.1f}s[/]")


@app.command()
def voices():
    """List available voices."""
    from .generators.voice import list_available_voices

    voices_list = list_available_voices()

    table = Table(title="Available Voices")
    table.add_column("Key", style="cyan")
    table.add_column("Name")
    table.add_column("Gender")
    table.add_column("Tone")
    table.add_column("Description", max_width=40)

    for v in voices_list:
        table.add_row(
            v["key"],
            v["name"],
            v["gender"],
            v["tone"],
            v["description"][:40] + "..." if len(v.get("description", "")) > 40 else v.get("description", ""),
        )

    console.print(table)


if __name__ == "__main__":
    app()
