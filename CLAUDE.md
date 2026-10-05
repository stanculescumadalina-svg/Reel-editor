# Reel editor

Vlog/storytelling reel editor: Claude watches B-roll (contact sheets), writes a story
plan, and the `reel` Python package turns it into a beat-synced CapCut desktop draft.

- Workflow for editing a reel: `.claude/skills/make-reel/SKILL.md`
- `reel/media.py`: ffprobe scan and contact sheets (`<clips>/_reel/`)
- `reel/beats.py`: numpy beat tracking and choosing a start point in the song
- `reel/plan.py`: plan.json → beat-aligned `Timeline` (pure, all times in µs)
- `reel/capcut.py`: `Timeline` → CapCut draft via pyCapCut
- `reel/styles.py`: style presets; names must exist in pyCapCut's metadata enums
- `reel/preview.py`: quick FFmpeg preview render

Run tests with `python -m pytest -q` (needs ffmpeg on PATH).
