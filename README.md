# Automated Mathematical YouTube Video Agent

The pipeline reads Excel prompts, generates a structured educational
script and visual scene plan with Groq, reviews mathematical quality, generates
safe Manim code, repairs render errors up to three times, renders an MP4, and
records progress in both SQLite and Excel, generates narration/metadata/a
thumbnail, and can automatically upload validated videos privately to YouTube.

## Architecture

```text
input/prompts.xlsx
  -> PromptManager + SQLite state
  -> Groq educational script (script.json)
  -> Groq visual plan (scene_plan.json)
  -> quality review (quality_review.json)
  -> Manim code (scene_vN.py and scene.py)
  -> AST safety validation
  -> Manim render / targeted repair loop
  -> ffprobe validation
  -> Edge TTS narration + FFmpeg synchronization
  -> metadata.json + 1280x720 thumbnail.png
  -> final validation
  -> resumable private YouTube upload
```

Each responsibility lives in a separate module under `src/`. LLM prompts are
plain text files under `prompts/`, so they can be improved without changing
pipeline code.

## Requirements

- Windows 10/11
- Python 3.11 (the project pins 3.11.9)
- `uv`
- FFmpeg and ffprobe on `PATH`
- Manim Community Edition 0.19.0 (installed by `uv sync`)
- A Groq API key

This Phase 1 prompt deliberately tells Manim to use `Text` instead of `Tex` or
`MathTex`, so LaTeX is not required yet. Install a LaTeX distribution later if
you want fully typeset equations.

## Setup on Windows

```powershell
cd D:\GenAI\NEW_LLM\utube
uv sync
Copy-Item .env.example .env
```

Edit `.env` and set:

```env
GROQ_API_KEY=your_key_here
DRY_RUN=true
VIDEOS_PER_DAY=1
MANIM_QUALITY=low_quality
```

The real `.env` is excluded from Git.

## Input workbook

The original `manim.xlsx` remains untouched. The working copy is
`input/prompts.xlsx`. On first run the program adds status and artifact columns
to the working copy and imports the 300 prompts into `database/agent.db`.

## Safe single-video commands

Process the existing Kaprekar prompt (Prompt ID 31):

```powershell
uv run python main.py --prompt-id 31
```

Or supply a one-off topic:

```powershell
uv run python main.py --topic "Animate Kaprekar's constant 6174"
```

The current milestone processes one prompt per invocation. `--limit 1` is
accepted for compatibility with the planned batch interface.

## Restart behavior

Completed `script.json` and `scene_plan.json` files are reused. Each generated
or repaired scene version is preserved. SQLite and Excel are updated after
important stages. A failed render does not erase earlier artifacts.

## Tests

```powershell
uv run python -m unittest discover -s tests -v
```

The tests cover Excel loading/status initialization, state database behavior,
duplicate normalization, and generated-code safety. Manim itself is checked by
a lightweight render smoke test during development rather than mocked deeply.

## YouTube OAuth and automatic upload

1. In Google Cloud Console, enable **YouTube Data API v3**.
2. Configure the OAuth consent screen.
3. Create an OAuth **Desktop app** credential.
4. Download its JSON to `secrets/client_secret.json`.
5. Authorize once:

```powershell
uv run python main.py --authorize-youtube
```

6. Change `DRY_RUN=false` in `.env`.
7. Run a safe batch:

```powershell
uv run python main.py --limit 1
```

Every fully prepared video is then uploaded automatically. Upload privacy
defaults to `private`; never change it casually. OAuth tokens and client secrets
are excluded from Git. Uploads use resumable chunks and bounded exponential
backoff for transient server errors.

For this workspace, the safe one-video production launcher is:

```powershell
.\run_private_batch.ps1
```

It processes at most one actionable prompt and forces private upload. This file
can later be invoked by Windows Task Scheduler. Custom thumbnails require the
YouTube channel to have custom-thumbnail access; if YouTube rejects a thumbnail,
the code preserves the already-uploaded video ID instead of uploading a duplicate.

To retry failed items:

```powershell
uv run python main.py --retry-failed --limit 1
```

## Always-on hourly deployment

The GitHub Actions workflow in `.github/workflows/hourly-video.yml` generates
and uploads one private video every hour (at minute 17). It can also be started
manually from the repository's Actions page. GitHub repository concurrency
prevents overlapping runs, while `database/agent.db` and `input/prompts.xlsx`
preserve upload progress between runners. Videos, logs, OAuth files, and API
keys are excluded from Git.
