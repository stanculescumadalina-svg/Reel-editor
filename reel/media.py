"""Probe clips with ffprobe and build contact sheets Claude can look at."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".3gp"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"}

WORK_DIR = "_reel"
FRAMES_PER_SHEET = 6  # 3 columns x 2 rows


@dataclass
class Clip:
    file: str                      # file name, relative to the clips folder
    kind: str                      # "video" or "image"
    width: int                     # display width (rotation applied)
    height: int                    # display height (rotation applied)
    duration: float                # seconds (0 for images)
    rotation: int = 0
    fps: float = 0.0
    has_audio: bool = False
    created: Optional[str] = None  # ISO timestamp from metadata, if any
    location: Optional[str] = None # ISO 6709 string from metadata, if any
    sheet: Optional[str] = None    # contact sheet path, relative to the clips folder
    sheet_times: list = field(default_factory=list)  # timestamp of each frame in the sheet

    @property
    def orientation(self) -> str:
        if self.width == self.height:
            return "square"
        return "portrait" if self.height > self.width else "landscape"


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise SystemExit(
                f"'{tool}' was not found. Install FFmpeg first "
                "(Windows: `winget install Gyan.FFmpeg`, then open a new terminal)."
            )


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout


def ffprobe(path: Path) -> dict:
    return json.loads(_run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]))


def _rotation(stream: dict) -> int:
    rot = stream.get("tags", {}).get("rotate")
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            rot = side["rotation"]
    try:
        return int(float(rot or 0)) % 360
    except ValueError:
        return 0


def _fps(stream: dict) -> float:
    num, _, den = (stream.get("avg_frame_rate") or "0/1").partition("/")
    try:
        return round(float(num) / float(den or 1), 2)
    except ZeroDivisionError:
        return 0.0


def probe(path: Path, folder: Path) -> Optional[Clip]:
    ext = path.suffix.lower()
    if ext not in VIDEO_EXTS | IMAGE_EXTS:
        return None
    info = ffprobe(path)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        return None
    tags = {k.lower(): v for k, v in info.get("format", {}).get("tags", {}).items()}
    rotation = _rotation(video)
    w, h = int(video.get("width", 0)), int(video.get("height", 0))
    if rotation in (90, 270):
        w, h = h, w
    is_image = ext in IMAGE_EXTS
    return Clip(
        file=path.relative_to(folder).as_posix(),
        kind="image" if is_image else "video",
        width=w,
        height=h,
        duration=0.0 if is_image else round(float(info["format"].get("duration", 0) or 0), 3),
        rotation=rotation,
        fps=0.0 if is_image else _fps(video),
        has_audio=any(s.get("codec_type") == "audio" for s in info.get("streams", [])),
        created=tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate"),
        location=tags.get("com.apple.quicktime.location.iso6709") or tags.get("location"),
    )


def make_sheet(clip: Clip, folder: Path, out_dir: Path) -> None:
    """Write a 3x2 grid of evenly spaced frames so Claude can 'watch' the clip."""
    src = folder / clip.file
    out = out_dir / (Path(clip.file).stem + ".jpg")
    if clip.kind == "image":
        _run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
              "-vf", "scale=480:-2", "-frames:v", "1", str(out)])
        clip.sheet_times = [0.0]
    else:
        n = FRAMES_PER_SHEET
        step = clip.duration / n
        clip.sheet_times = [round(step * (i + 0.5), 2) for i in range(n)]
        # Seek to each timestamp separately: fast and accurate even for long clips.
        inputs: list[str] = []
        for t in clip.sheet_times:
            inputs += ["-ss", f"{t:.2f}", "-i", str(src)]
        scaled = "".join(f"[{i}:v]scale=360:360:force_original_aspect_ratio=decrease,"
                         f"pad=360:360:(ow-iw)/2:(oh-ih)/2,setsar=1[f{i}];" for i in range(n))
        grid = "".join(f"[f{i}]" for i in range(n))
        layout = "|".join(f"{(i % 3) * 360}_{(i // 3) * 360}" for i in range(n))
        _run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
              f"{scaled}{grid}xstack=inputs={n}:layout={layout}[out]",
              "-map", "[out]", "-frames:v", "1", "-q:v", "4", str(out)])
    clip.sheet = out.relative_to(folder).as_posix()


def scan(folder: Path) -> dict:
    """Probe every clip in `folder`, build contact sheets, and write `_reel/clips.json`."""
    require_ffmpeg()
    folder = folder.resolve()
    work = folder / WORK_DIR
    sheets = work / "sheets"
    sheets.mkdir(parents=True, exist_ok=True)

    clips: list[Clip] = []
    music: list[str] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() in AUDIO_EXTS:
            music.append(path.name)
            continue
        try:
            clip = probe(path, folder)
            if clip is None:
                continue
            make_sheet(clip, folder, sheets)
        except (RuntimeError, ValueError, KeyError) as err:
            print(f"  skipped {path.name}: {str(err).splitlines()[-1]}")
            continue
        clips.append(clip)

    # Chronological order is the natural starting point for a vlog story.
    clips.sort(key=lambda c: (c.created is None, c.created or "", c.file))
    data = {
        "folder": str(folder),
        "music": music,
        "clips": [asdict(c) | {"orientation": c.orientation} for c in clips],
    }
    (work / "clips.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data
