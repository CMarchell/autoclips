# AutoClips - AI Short-Form Video Generator

## Project Overview

AutoClips is an AI-powered pipeline for generating short-form vertical videos (30-70 seconds, 9:16 aspect ratio) for TikTok, YouTube Shorts, and Instagram Reels. The system is designed to be **agent-friendly** so Claude Code can create, modify, and manage videos autonomously.

## Quick Start

```bash
# Install dependencies
uv sync

# Set up environment variables (copy and fill in API keys)
cp .env.example .env

# Generate a video
uv run autoclips create "5 budgeting tips for beginners" --niche finance

# List draft projects
uv run autoclips list --status draft

# Approve a video
uv run autoclips approve <project_id>
```

---

## Installation & Setup Guide

### Prerequisites

- **Python 3.11+** - Required for the project
- **uv** - Python package manager (recommended over pip)
- **FFmpeg** - Required for video processing
- **Git** - For version control

### Step 1: Install uv (Python Package Manager)

If you don't have `uv` installed:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

### Step 2: Install FFmpeg

FFmpeg is required for video processing (MoviePy depends on it).

**Windows:**
```bash
# Option 1: Chocolatey (recommended)
choco install ffmpeg

# Option 2: Scoop
scoop install ffmpeg

# Option 3: Manual download
# Download from https://ffmpeg.org/download.html
# Extract and add bin/ folder to your PATH
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Verify installation:**
```bash
ffmpeg -version
```

### Step 3: Clone and Install Dependencies

```bash
# Navigate to your project directory
cd D:\Git\autoclips   # or wherever your project is

# Install Python dependencies
uv sync

# This creates a virtual environment and installs all packages from pyproject.toml
```

### Step 4: Set Up API Keys

Copy the example environment file and add your API keys:

```bash
# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Required: At least one AI provider
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# Required: Text-to-speech
ELEVENLABS_API_KEY=xxxxxxxxxxxxx

# Required: Stock footage
PEXELS_API_KEY=xxxxxxxxxxxxx

# Optional: Default AI provider (anthropic or openai)
AI_PROVIDER=anthropic
```

#### Getting API Keys:

| Service | URL | Notes |
|---------|-----|-------|
| **Anthropic** | https://console.anthropic.com/ | Claude API for script generation |
| **OpenAI** | https://platform.openai.com/api-keys | Alternative to Anthropic |
| **ElevenLabs** | https://elevenlabs.io/ | Sign up → Profile → API Key |
| **Pexels** | https://www.pexels.com/api/ | Free, just needs registration |

### Step 5: Add Background Music

Add royalty-free music tracks to the mood folders:

```
assets/
└── music/
    ├── energetic/    # Upbeat tracks for finance, motivation
    │   └── track1.mp3
    ├── calm/         # Relaxed tracks for lifestyle, wellness
    │   └── track1.mp3
    └── dramatic/     # Intense tracks for storytelling
        └── track1.mp3
```

**Free music sources:**
- [Pixabay Music](https://pixabay.com/music/) - Free, no attribution required
- [Uppbeat](https://uppbeat.io/) - Free tier available
- [Mixkit](https://mixkit.co/free-stock-music/) - Free, no attribution
- [YouTube Audio Library](https://studio.youtube.com/channel/audio) - Free for YouTube use

**Tips:**
- Add 5-10 tracks per mood for variety
- Keep tracks 2-3 minutes long (they'll loop automatically)
- Use MP3 or WAV format

### Step 6: Verify Installation

```bash
# Check CLI is working
uv run autoclips --help

# List available voices
uv run autoclips voices

# Generate some topic ideas (tests AI connection)
uv run autoclips ideas --niche finance --count 3
```

### Step 7: Create Your First Video

```bash
# Create a video project
uv run autoclips create "3 money habits of millionaires" --niche finance

# The output will show a project ID like: 2024-01-15_3-money-habits_abc12345

# Check the project status
uv run autoclips status 2024-01-15_3-money-habits_abc12345

# View the generated script
uv run autoclips script 2024-01-15_3-money-habits_abc12345

# Render a preview
uv run autoclips preview 2024-01-15_3-money-habits_abc12345

# If satisfied, approve and render final
uv run autoclips approve 2024-01-15_3-money-habits_abc12345
```

---

## CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `create` | Create a new video | `autoclips create "topic" --niche finance` |
| `ideas` | Generate topic ideas | `autoclips ideas --niche finance --count 5` |
| `list` | List all projects | `autoclips list --status draft` |
| `status` | Get project details | `autoclips status <project_id>` |
| `script` | View project script | `autoclips script <project_id>` |
| `footage` | View footage clips | `autoclips footage <project_id>` |
| `preview` | Render preview video | `autoclips preview <project_id>` |
| `approve` | Approve and render final | `autoclips approve <project_id>` |
| `kill` | Kill/delete project | `autoclips kill <project_id> --delete` |
| `voices` | List available voices | `autoclips voices` |
| `update-script` | Update script from file | `autoclips update-script <id> script.txt` |
| `remove-footage` | Remove a footage clip | `autoclips remove-footage <id> "running"` |
| `regen-voice` | Regenerate voiceover | `autoclips regen-voice <project_id>` |

---

## Architecture

### Pipeline Flow
```
Idea Generation → Script Writing → Voice Generation → B-Roll Fetching → Video Assembly → Metadata Export
```

### Key Design Principles
1. **Staged Pipeline**: Each video is a "project" with saved state at every step
2. **Agent-Friendly**: All operations exposed as callable functions
3. **Niche-Agnostic**: Works with any topic; niche configs are optional enhancements
4. **Deduplication**: Tracks used topics and footage to avoid repetition
5. **Review Workflow**: Videos go through draft → preview → approved states

## Project Structure

```
autoclips/
├── config/
│   ├── settings.yaml          # API keys reference, defaults
│   ├── voices.yaml            # ElevenLabs voice catalog
│   └── niches/
│       ├── _default.yaml      # Fallback for ad-hoc topics
│       └── finance.yaml       # Niche-specific prompts/settings
├── assets/
│   └── music/                 # Royalty-free tracks by mood
│       ├── energetic/
│       ├── calm/
│       └── dramatic/
├── projects/                  # Active video projects (drafts, in-progress)
├── output/                    # Approved final videos
├── src/
│   ├── core/
│   │   ├── pipeline.py        # Main orchestration
│   │   ├── project.py         # Project state management
│   │   └── database.py        # SQLite tracking
│   ├── generators/
│   │   ├── ideas.py           # Topic idea generation
│   │   ├── script.py          # Script writing
│   │   ├── voice.py           # ElevenLabs TTS
│   │   └── metadata.py        # Titles, descriptions, tags
│   ├── media/
│   │   ├── footage.py         # Pexels API fetching
│   │   ├── captions.py        # Word-by-word animated captions
│   │   └── assembler.py       # MoviePy video composition
│   └── agents/
│       └── functions.py       # All agent-callable functions
├── data/
│   └── autoclips.db           # SQLite database
├── main.py                    # CLI entry point (Typer)
└── pyproject.toml             # uv/Python dependencies
```

## Agent-Callable Functions

These functions are designed to be called by Claude Code or other AI agents:

### Discovery & Creation
- `create_video(topic, niche=None)` - Create a new video project
- `generate_ideas(niche, count=5)` - Get topic suggestions
- `list_projects(status="draft")` - List projects by status

### Inspection
- `get_project_status(project_id)` - Full project state summary
- `get_script(project_id)` - Read current script
- `get_footage_list(project_id)` - List all b-roll with descriptions/keywords

### Modifications
- `update_script(project_id, new_script)` - Replace entire script
- `update_script_section(project_id, find, replace)` - Partial script edit
- `remove_footage(project_id, clip_name_or_keyword)` - Remove specific b-roll
- `replace_footage(project_id, clip_id, new_keyword)` - Swap b-roll clip
- `change_voice(project_id, voice_id)` - Use different ElevenLabs voice
- `change_music(project_id, mood_or_track)` - Change background music
- `regenerate_voiceover(project_id)` - Re-run TTS after script changes

### Pipeline Control
- `render_preview(project_id)` - Generate preview video
- `approve_video(project_id)` - Render final and mark complete
- `kill_video(project_id)` - Delete project entirely

## Video Project State

Each video project lives in `projects/<project_id>/` with:

```
project_id/
├── project.json        # Full state (settings, status, timestamps)
├── script.txt          # The voiceover script (editable)
├── voiceover.mp3       # Generated TTS audio
├── footage/            # Downloaded b-roll clips
│   ├── 001_keyword.mp4
│   ├── 002_keyword.mp4
│   └── ...
├── timeline.json       # Footage timing/sequencing
├── preview.mp4         # Draft render
├── final.mp4           # Approved final render
└── metadata.json       # Title, description, tags (platform-ready)
```

### Project Statuses
- `draft` - Script and footage selected, awaiting review
- `preview` - Preview video rendered, ready for approval
- `approved` - Final video rendered, ready for upload
- `killed` - Marked for deletion

## Configuration

### Environment Variables (.env)
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
PEXELS_API_KEY=...
```

### Niche Configuration (config/niches/finance.yaml)
```yaml
name: finance
display_name: "Finance & Money Tips"

# Voice settings
voice:
  voice_id: "pNInz6obpgDQGcFmaJgB"  # ElevenLabs voice ID
  stability: 0.5
  similarity_boost: 0.75

# Script generation prompts
prompts:
  system: "You are a knowledgeable financial advisor creating short, actionable money tips..."
  style: "conversational, confident, actionable"

# Video settings
music_mood: "energetic"
footage_keywords_boost: ["money", "savings", "investing", "wealth"]

# Metadata
default_hashtags: ["#finance", "#moneytips", "#investing"]
```

## Common Agent Workflows

### Creating Videos on a New Topic
```
User: "Make 3 videos about coffee benefits"

Agent should:
1. Call create_video("health benefits of coffee")
2. Call create_video("coffee and productivity")
3. Call create_video("best time to drink coffee")
4. Report project IDs and offer to show previews
```

### Modifying a Video
```
User: "Remove the b-roll showing a person running in video 002"

Agent should:
1. Call get_footage_list("002") to see clips
2. Identify clip with "running" keyword
3. Call remove_footage("002", "003_running.mp4")
4. Call render_preview("002")
5. Report completion
```

### Batch Operations
```
User: "Approve all draft videos"

Agent should:
1. Call list_projects(status="draft")
2. For each project, call approve_video(project_id)
3. Report results
```

## Technical Notes

### Video Specifications
- **Duration**: 30-70 seconds
- **Aspect Ratio**: 9:16 (vertical)
- **Resolution**: 1080x1920
- **FPS**: 30
- **Captions**: Word-by-word animated, white text with black outline

### API Usage
- **ElevenLabs**: ~1000 chars per 30 sec video, Creator tier recommended ($22/mo)
- **Claude/OpenAI**: ~500-1000 tokens per video for script generation
- **Pexels**: Free, rate limited to 200 requests/hour

### Deduplication
The SQLite database tracks:
- Topics used (avoid repeating same topic within 30 days)
- Pexels video IDs used (avoid reusing same clip within 10 videos)
- Scripts (full text for reference)

## Development Commands

```bash
# Install dependencies
uv sync

# Run CLI
uv run autoclips --help

# Run with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Lint/format
uv run ruff check .
uv run ruff format .
```

## Future Enhancements (Not Yet Implemented)
- [ ] Programmatic upload to TikTok, YouTube, Instagram
- [ ] Scheduled/cron-based automatic video generation
- [ ] A/B testing different hooks/thumbnails
- [ ] Analytics tracking for video performance
- [ ] Multi-language support

## Troubleshooting

### MoviePy/FFmpeg Issues
Ensure FFmpeg is installed and in PATH:
```bash
# Windows (with chocolatey)
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

### ElevenLabs Rate Limits
If hitting rate limits, the system will retry with exponential backoff. Consider upgrading plan for higher throughput.

### Pexels No Results
If a keyword returns no footage, the system will try:
1. Simplified keywords
2. Related/synonym keywords
3. Fallback to generic "abstract" footage
