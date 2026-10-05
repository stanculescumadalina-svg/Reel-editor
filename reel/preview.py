"""Render a rough MP4 of the timeline with FFmpeg: cuts, framing and music only.

It's a fast way to check pacing and story order on your phone before opening
CapCut. Text, transitions, filters and effects only appear in the CapCut draft.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .plan import US, Timeline

W, H, FPS = 720, 1280, 30


def render_preview(tl: Timeline, out: Path) -> Path:
    inputs: list[str] = []
    chains: list[str] = []
    for i, shot in enumerate(tl.shots):
        dur = shot.duration / US
        if shot.kind == "image":
            inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(shot.path)]
            base = f"[{i}:v]"
        else:
            src_len = dur * shot.speed
            inputs += ["-ss", f"{shot.source_in / US:.3f}", "-t", f"{src_len:.3f}", "-i", str(shot.path)]
            base = f"[{i}:v]setpts=(PTS-STARTPTS)/{shot.speed:.4f},"
        if shot.blur_background:
            chains.append(
                f"{base}split[a{i}][b{i}];"
                f"[a{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:2[bg{i}];"
                f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,"
            )
        else:
            chains.append(f"{base}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},")
        # Pin every shot to its exact beat length so the cuts stay on the music.
        chains[-1] += (f"fps={FPS},setsar=1,format=yuv420p,"
                       f"tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},"
                       f"setpts=PTS-STARTPTS[v{i}];")
    n = len(tl.shots)
    graph = "".join(chains) + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]"
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs]
    maps = ["-map", "[vout]"]
    if tl.music is not None:
        cmd += ["-ss", f"{tl.music_offset / US:.3f}", "-i", str(tl.music)]
        total = tl.duration / US
        graph += f";[{n}:a]atrim=duration={total:.3f},afade=t=out:st={max(0, total - 0.6):.3f}:d=0.6[aout]"
        maps += ["-map", "[aout]"]
    cmd += ["-filter_complex", graph, *maps, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{tl.duration / US:.3f}", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg preview failed:\n{result.stderr.strip()[-2000:]}")
    return out
