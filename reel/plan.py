"""Turn Claude's story plan (plan.json) into an exact, beat-aligned timeline.

Everything here is pure data: no CapCut and no rendering, so it's easy to test.
All timeline values are integer microseconds, the unit CapCut uses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import beats as beatlib
from .media import WORK_DIR
from .styles import Style, get_style

US = 1_000_000
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 30
MAX_LABEL_US = int(2.6 * US)   # a label holds until the next one, but no longer than this

# Which on-screen text each text_mode keeps.
TEXT_MODES = {
    "none": set(),                          # clean footage + music only
    "hook": {"hook", "outro"},              # just the opening line (and closing line, if any)
    "story": {"hook", "outro", "label"},    # plus scene labels wherever the plan has them
}


@dataclass
class Shot:
    clip: str
    path: Path
    kind: str
    width: int
    height: int
    start: int                 # timeline position (µs)
    duration: int              # timeline duration (µs)
    source_in: int             # where to start in the clip (µs)
    speed: float
    fill_scale: float          # extra scale on top of CapCut's fit-to-canvas (1.0 = fit)
    blur_background: bool
    volume: float
    emphasis: bool
    transition: Optional[str]  # transition into the NEXT shot
    note: str = ""


@dataclass
class Caption:
    text: str
    start: int
    duration: int
    role: str                  # "hook", "label" or "outro"


@dataclass
class Timeline:
    title: str
    style: Style
    shots: list[Shot]
    captions: list[Caption]
    duration: int
    bpm: float
    music: Optional[Path]
    music_offset: int          # where in the song the reel starts (µs)
    caption_text: str
    warnings: list[str] = field(default_factory=list)
    text_mode: str = "story"
    unused: list[str] = field(default_factory=list)         # clips in the folder the reel doesn't use
    skipped: dict[str, str] = field(default_factory=dict)   # Claude's reasons for leaving clips out


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if not plan.get("scenes"):
        problems.append("plan has no scenes")
    for i, scene in enumerate(plan.get("scenes", [])):
        if "clip" not in scene:
            problems.append(f"scene {i + 1} has no 'clip'")
        if int(scene.get("beats", 1)) < 1:
            problems.append(f"scene {i + 1}: 'beats' must be at least 1")
    if problems:
        raise ValueError("Invalid plan:\n  - " + "\n  - ".join(problems))
    return plan


def clips_folder_for(plan_path: Path, plan: dict) -> Path:
    if plan.get("folder"):
        return Path(plan["folder"])
    # Plans normally live in <clips>/_reel/plan.json
    parent = plan_path.resolve().parent
    return parent.parent if parent.name == WORK_DIR else parent


def load_clip_index(folder: Path) -> dict[str, dict]:
    index_file = folder / WORK_DIR / "clips.json"
    if not index_file.exists():
        raise SystemExit(f"No clips.json in {index_file.parent}. Run `python -m reel scan \"{folder}\"` first.")
    data = json.loads(index_file.read_text(encoding="utf-8"))
    return {c["file"]: c for c in data["clips"]}


def fill_scale(width: int, height: int) -> float:
    """Scale that turns CapCut's default 'fit' placement into 'fill the 9:16 frame'."""
    fit = min(CANVAS_W / width, CANVAS_H / height)
    fill = max(CANVAS_W / width, CANVAS_H / height)
    return fill / fit


def _window(scene: dict, info: dict) -> tuple[float, float]:
    """The usable part of a clip for this scene, in seconds: `in` to `out` (default: the whole clip)."""
    if info["kind"] != "video":
        return 0.0, 0.0
    end = max(0.0, info["duration"] - 0.05)  # stay clear of the last frame
    w_in = min(max(0.0, float(scene.get("in", 0.0))), end)
    w_out = min(float(scene["out"]), end) if scene.get("out") is not None else end
    if w_out <= w_in:
        raise ValueError(f"Scene with clip '{scene['clip']}': 'out' ({w_out}s) must be after 'in' ({w_in}s)")
    return w_in, w_out


def _seconds_to_beat_index(grid: beatlib.BeatGrid, seconds: float) -> int:
    for i, b in enumerate(grid.beats):
        if b >= seconds - 0.05:
            return i
    return 0


def build_timeline(plan: dict, folder: Path, grid: Optional[beatlib.BeatGrid] = None) -> Timeline:
    """Resolve the plan against real clip lengths and the music's beat grid."""
    style = get_style(plan.get("style"))
    clips = load_clip_index(folder)
    warnings: list[str] = []

    scenes = plan["scenes"]
    for s in scenes:
        if s["clip"] not in clips:
            raise ValueError(f"Clip '{s['clip']}' isn't in clips.json. Known clips: {', '.join(clips)}")

    music = Path(folder, plan["music"]) if plan.get("music") else None
    if music is not None and not music.exists():
        raise ValueError(f"Music file not found: {music}")
    if grid is None:
        grid = beatlib.analyze(music) if music else beatlib.fixed_grid(float(plan.get("bpm", 120)), 600)

    # Each scene may only use footage inside its usable window [in, out].
    windows = [_window(s, clips[s["clip"]]) for s in scenes]
    scene_beats = []
    for i, (scene, (w_in, w_out)) in enumerate(zip(scenes, windows)):
        n_beats = int(scene.get("beats", style.beats_per_cut))
        if clips[scene["clip"]]["kind"] == "video":
            speed = float(scene.get("speed", 1.0))
            fits = int((w_out - w_in) / (grid.period * speed * 1.02))  # 2% slack for tempo wobble
            if 1 <= fits < n_beats:
                warnings.append(f"scene {i + 1} ({scene['clip']}): only {w_out - w_in:.1f}s usable "
                                f"({w_in:.1f}-{w_out:.1f}s), shortened from {n_beats} to {fits} beats")
                n_beats = fits
        scene_beats.append(n_beats)
    total_beats = sum(scene_beats)

    start_setting = plan.get("music_start", "auto")
    if music is None:
        start_index = 0
    elif start_setting == "auto":
        start_index = beatlib.pick_start_beat(grid, total_beats)
    else:
        start_index = _seconds_to_beat_index(grid, float(start_setting))
    # Snap cut points to whole 30fps frames so CapCut never sees sub-frame segments.
    times = [int(round(t * FPS)) * US // FPS for t in beatlib.beat_times(grid, start_index, total_beats)]
    music_offset = int(round(grid.beats[start_index] * US)) if music and grid.beats else 0

    shots: list[Shot] = []
    cursor = 0
    n_transitions = 0
    for i, (scene, n_beats) in enumerate(zip(scenes, scene_beats)):
        info = clips[scene["clip"]]
        start, end = times[cursor], times[cursor + n_beats]
        cursor += n_beats
        duration = end - start
        speed = float(scene.get("speed", 1.0))
        w_in, w_out = (int(round(t * US)) for t in windows[i])
        source_in = w_in

        if info["kind"] == "video":
            usable = w_out - w_in
            need = int(duration * speed)
            if need > usable:
                # Even one beat doesn't fit: slow the footage down rather than leave the window.
                speed = round(max(0.1, usable / duration), 3)
                warnings.append(f"scene {i + 1} ({scene['clip']}): usable part too short for "
                                f"{n_beats} beat(s), slowed to {speed}x")
                need = int(duration * speed)
            if scene.get("align") == "end":
                source_in = max(w_in, w_out - need)
        else:
            speed, source_in = 1.0, 0

        frame = scene.get("frame", "auto")
        landscape = info["width"] > info["height"]
        if frame == "fit" or (frame == "auto" and landscape):
            scale, blur = 1.0, True
        else:
            scale, blur = fill_scale(info["width"], info["height"]), False

        transition = scene.get("transition")
        if transition == "none" or i == len(scenes) - 1:
            transition = None
        elif transition is None and style.transition_every:
            if (i + 1) % style.transition_every == 0:
                transition = style.transitions[n_transitions % len(style.transitions)]
                n_transitions += 1

        has_music = music is not None
        volume = 0.8 if scene.get("keep_audio") else (0.0 if has_music else 0.15)

        shots.append(Shot(
            clip=scene["clip"], path=folder / scene["clip"], kind=info["kind"],
            width=info["width"], height=info["height"],
            start=start, duration=duration, source_in=source_in, speed=speed,
            fill_scale=scale, blur_background=blur, volume=volume,
            emphasis=bool(scene.get("emphasis")), transition=transition,
            note=scene.get("note", ""),
        ))

    total = times[total_beats]
    text_mode = plan.get("text_mode", "story")
    if text_mode not in TEXT_MODES:
        raise ValueError(f"text_mode must be one of: {', '.join(TEXT_MODES)}")
    captions = [c for c in _captions(plan, shots, scenes, times, total) if c.role in TEXT_MODES[text_mode]]
    used = {s["clip"] for s in scenes}
    unused = [name for name in clips if name not in used]
    caption_text = plan.get("caption", "").strip()
    if plan.get("hashtags"):
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in plan["hashtags"])
        caption_text = f"{caption_text}\n\n{tags}".strip()

    return Timeline(
        title=plan.get("title", "My reel"), style=style, shots=shots, captions=captions,
        duration=total, bpm=grid.bpm, music=music, music_offset=music_offset,
        caption_text=caption_text, warnings=warnings,
        text_mode=text_mode, unused=unused, skipped=dict(plan.get("skipped") or {}),
    )


def _captions(plan: dict, shots: list[Shot], scenes: list[dict], times: list[int], total: int) -> list[Caption]:
    out: list[Caption] = []
    hook = (plan.get("hook") or "").strip()
    hook_end = 0
    if hook:
        hook_beats = int(plan.get("hook_beats", 4))
        hook_end = times[min(hook_beats, len(times) - 1)]
        hook_end = max(hook_end, min(total, int(1.8 * US)))  # always long enough to read
        out.append(Caption(hook, 0, hook_end, "hook"))

    outro = (plan.get("outro") or "").strip()
    outro_start = total
    if outro:
        outro_start = max(hook_end, shots[-1].start, total - int(2.0 * US))
        out.append(Caption(outro, outro_start, total - outro_start, "outro"))

    # Scene labels: hold each one until the next label, within readable bounds.
    labelled = [(shot.start, scene["text"].strip()) for shot, scene in zip(shots, scenes)
                if (scene.get("text") or "").strip()]
    # They sit low on screen, so they may share the screen with the hook at the top.
    for k, (start, text) in enumerate(labelled):
        next_start = labelled[k + 1][0] if k + 1 < len(labelled) else outro_start
        end = min(start + MAX_LABEL_US, next_start, outro_start)
        if end - start >= int(0.6 * US):
            out.append(Caption(text, start, end - start, "label"))
    return out
