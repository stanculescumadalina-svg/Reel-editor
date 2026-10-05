"""Write a Timeline into a CapCut desktop draft using pyCapCut."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

import pycapcut as cc
from pycapcut import ClipSettings, KeyframeProperty, Timerange

from .plan import CANVAS_H, CANVAS_W, FPS, US, Caption, Shot, Timeline

# Vertical positions (CapCut units: 1.0 = top edge, -1.0 = bottom edge), kept
# inside Instagram's safe zone so the like/comment buttons don't cover text.
TEXT_Y = {"hook": 0.32, "label": -0.38, "outro": 0.05}


def default_drafts_folder() -> Optional[Path]:
    """CapCut desktop's default drafts location, if it exists on this computer."""
    env = os.environ.get("CAPCUT_DRAFTS")
    if env:
        return Path(env)
    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.append(Path(local, "CapCut", "User Data", "Projects", "com.lveditor.draft"))
    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft")
    return next((c for c in candidates if c.exists()), None)


def safe_draft_name(title: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip().rstrip(".")
    return name[:80] or "My reel"


def _material(shot: Shot) -> cc.VideoMaterial:
    mat = cc.VideoMaterial(str(shot.path))
    # pymediainfo reports stored (unrotated) dimensions; phone clips are often stored
    # sideways with a rotation flag, so use the display size from our ffprobe scan.
    mat.width, mat.height = shot.width, shot.height
    return mat


def _video_segment(shot: Shot, style, period_us: int) -> cc.VideoSegment:
    seg = cc.VideoSegment(
        _material(shot),
        Timerange(shot.start, shot.duration),
        source_timerange=Timerange(shot.source_in, int(round(shot.duration * shot.speed))) if shot.kind == "video" else None,
        volume=shot.volume,
        clip_settings=ClipSettings(scale_x=shot.fill_scale, scale_y=shot.fill_scale),
    )
    if shot.blur_background:
        seg.add_background_filling("blur", 0.375)
    if style.punch_zoom > 1.0:
        seg.add_keyframe(KeyframeProperty.uniform_scale, 0, shot.fill_scale)
        seg.add_keyframe(KeyframeProperty.uniform_scale, shot.duration, shot.fill_scale * style.punch_zoom)
    if shot.emphasis:
        seg.add_animation(cc.IntroType[style.emphasis_intro], duration=min(int(0.5 * US), shot.duration // 2))
    if shot.transition:
        # Keep transitions snappy so they never smear across more than ~3/4 of a beat.
        seg.add_transition(cc.TransitionType[shot.transition], duration=min(int(0.5 * US), int(period_us * 0.75)))
    return seg


def _text_segment(cap: Caption, style) -> cc.TextSegment:
    is_hook = cap.role in ("hook", "outro")
    seg = cc.TextSegment(
        cap.text,
        Timerange(cap.start, cap.duration),
        font=cc.FontType[style.hook_font if is_hook else style.label_font],
        style=cc.TextStyle(
            size=style.hook_size if is_hook else style.label_size,
            bold=is_hook,
            color=style.text_color,
            align=1,
            auto_wrapping=True,
            max_line_width=0.78,
        ),
        clip_settings=ClipSettings(transform_y=TEXT_Y[cap.role]),
        border=cc.TextBorder(color=(0, 0, 0), width=35.0, alpha=0.9),
        background=(cc.TextBackground(color=style.label_box, alpha=0.55, round_radius=0.25)
                    if style.label_box and cap.role == "label" else None),
    )
    anim = min(int(0.4 * US), cap.duration // 3)
    seg.add_animation(cc.TextIntro[style.text_intro], duration=anim)
    if cap.duration > int(1.2 * US):
        seg.add_animation(cc.TextOutro[style.text_outro], duration=min(int(0.3 * US), anim))
    return seg


def write_draft(tl: Timeline, drafts_folder: Path, name: Optional[str] = None) -> Path:
    drafts_folder.mkdir(parents=True, exist_ok=True)
    draft_name = safe_draft_name(name or tl.title)
    folder = cc.DraftFolder(str(drafts_folder))
    script = folder.create_draft(draft_name, CANVAS_W, CANVAS_H, fps=FPS, allow_replace=True)
    style = tl.style
    period_us = int(60 / tl.bpm * US)

    script.add_track(cc.TrackType.video, "main")
    for shot in tl.shots:
        script.add_segment(_video_segment(shot, style, period_us), "main")

    if tl.music is not None:
        music = cc.AudioMaterial(str(tl.music))
        length = min(tl.duration, music.duration - tl.music_offset)
        seg = cc.AudioSegment(music, Timerange(0, length),
                              source_timerange=Timerange(tl.music_offset, length), volume=1.0)
        seg.add_fade(0, min(int(0.6 * US), length // 4))
        script.add_track(cc.TrackType.audio, "music")
        script.add_segment(seg, "music")

    if style.filter:
        script.add_track(cc.TrackType.filter, "look")
        script.add_filter(cc.FilterType[style.filter], Timerange(0, tl.duration), "look",
                          intensity=style.filter_intensity)

    if style.emphasis_effect and any(s.emphasis for s in tl.shots):
        script.add_track(cc.TrackType.effect, "fx")
        for shot in tl.shots:
            if shot.emphasis:
                script.add_effect(cc.VideoSceneEffectType[style.emphasis_effect],
                                  Timerange(shot.start, shot.duration), "fx")

    titles = [c for c in tl.captions if c.role != "label"]
    labels = [c for c in tl.captions if c.role == "label"]
    for track, caps in (("labels", labels), ("titles", titles)):
        if caps:
            script.add_track(cc.TrackType.text, track)
            for cap in sorted(caps, key=lambda c: c.start):
                script.add_segment(_text_segment(cap, style), track)

    script.save()
    return drafts_folder / draft_name
