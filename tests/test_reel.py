import json
import shutil
import subprocess

import pycapcut as cc
import pytest

from reel import beats as beatlib
from reel.capcut import safe_draft_name, write_draft
from reel.media import scan
from reel.plan import US, build_timeline, fill_scale
from reel.styles import STYLES

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    ff("-f", "lavfi", "-i", "testsrc2=size=540x960:rate=30", "-t", "4", "-pix_fmt", "yuv420p", str(d / "portrait.mp4"))
    ff("-f", "lavfi", "-i", "testsrc=size=960x540:rate=30", "-t", "3", "-pix_fmt", "yuv420p", str(d / "wide.mp4"))
    ff("-display_rotation", "90", "-i", str(d / "wide.mp4"), "-c", "copy", str(d / "phone.mov"))
    ff("-f", "lavfi", "-i", "color=c=orange:size=600x800", "-frames:v", "1", str(d / "photo.jpg"))
    # 120 BPM kick drum, louder in the second half.
    ff("-f", "lavfi", "-i", "aevalsrc='sin(2*PI*60*t)*exp(-30*mod(t\\,0.5))*(0.4+0.6*gte(t\\,15))':s=22050:d=30",
       "-c:a", "libmp3lame", str(d / "song.mp3"))
    scan(d)
    return d


def test_style_effects_exist_in_capcut_metadata():
    for s in STYLES.values():
        for t in s.transitions:
            cc.TransitionType[t]
        cc.IntroType[s.emphasis_intro]
        cc.TextIntro[s.text_intro]
        cc.TextOutro[s.text_outro]
        cc.FontType[s.hook_font]
        cc.FontType[s.label_font]
        if s.filter:
            cc.FilterType[s.filter]
        if s.emphasis_effect:
            cc.VideoSceneEffectType[s.emphasis_effect]


def test_fill_scale():
    assert fill_scale(1080, 1920) == pytest.approx(1.0)
    assert fill_scale(1920, 1080) == pytest.approx((1920 / 1080) ** 2)


def test_draft_name_is_windows_safe():
    assert safe_draft_name('Lisbon: day 1 / "weekend"?') == "Lisbon day 1  weekend"


def test_fixed_grid_and_start():
    grid = beatlib.fixed_grid(120, 10)
    assert grid.beats[:3] == [0.0, 0.5, 1.0]
    assert beatlib.beat_times(grid, 0, 4) == [0.0, 0.5, 1.0, 1.5, 2.0]


@needs_ffmpeg
def test_scan_applies_rotation(clips):
    data = json.loads((clips / "_reel" / "clips.json").read_text())
    by_name = {c["file"]: c for c in data["clips"]}
    assert (by_name["phone.mov"]["width"], by_name["phone.mov"]["height"]) == (540, 960)
    assert by_name["wide.mp4"]["orientation"] == "landscape"
    assert by_name["photo.jpg"]["kind"] == "image"
    assert data["music"] == ["song.mp3"]
    assert all((clips / c["sheet"]).exists() for c in data["clips"])


@needs_ffmpeg
def test_beat_tracking_finds_tempo_and_loud_part(clips):
    grid = beatlib.analyze(clips / "song.mp3")
    assert grid.bpm == pytest.approx(120, abs=2)
    assert grid.beats[beatlib.pick_start_beat(grid, 16)] >= 13


@needs_ffmpeg
def test_timeline_is_beat_aligned_and_respects_clip_length(clips):
    plan = {
        "title": "test", "style": "punchy", "music": "song.mp3", "hook": "POV: test",
        "scenes": [
            {"clip": "portrait.mp4", "beats": 2, "text": "SAT · 10:00"},
            {"clip": "wide.mp4", "in": 2.5, "beats": 2},           # `in` too late: must be pulled back
            {"clip": "photo.jpg", "beats": 1},
            {"clip": "phone.mov", "beats": 16},                    # 8s from a 3s clip: must slow down
        ],
        "outro": "follow for more",
    }
    tl = build_timeline(plan, clips)
    beat = 0.5 * US
    assert tl.shots[0].start == 0
    for a, b in zip(tl.shots, tl.shots[1:]):
        assert a.start + a.duration == b.start                 # no gaps or overlaps
    assert [round(s.duration / beat) for s in tl.shots] == [2, 2, 1, 16]
    wide = tl.shots[1]
    assert wide.source_in + wide.duration * wide.speed <= 3 * US
    assert wide.blur_background and not tl.shots[0].blur_background
    assert tl.shots[3].speed < 0.4 and tl.warnings
    assert {c.role for c in tl.captions} == {"hook", "label", "outro"}
    assert tl.music_offset >= 13 * US


@needs_ffmpeg
@pytest.mark.parametrize("style", list(STYLES))
def test_write_draft_every_style(clips, tmp_path, style):
    plan = {
        "title": f"reel {style}", "style": style, "music": "song.mp3", "hook": "hook text",
        "scenes": [{"clip": "portrait.mp4", "beats": 2, "emphasis": True, "text": "label"},
                   {"clip": "wide.mp4", "beats": 2, "transition": "Whip_Tear"},
                   {"clip": "photo.jpg", "beats": 2, "emphasis": True},
                   {"clip": "phone.mov", "beats": 4}],
        "outro": "bye",
    }
    path = write_draft(build_timeline(plan, clips), tmp_path)
    draft = json.loads((path / "draft_content.json").read_text(encoding="utf-8"))
    assert (path / "draft_meta_info.json").exists()
    assert (draft["canvas_config"]["width"], draft["canvas_config"]["height"]) == (1080, 1920)
    video = next(t for t in draft["tracks"] if t["type"] == "video")
    assert len(video["segments"]) == 4
    assert any(t["type"] == "audio" for t in draft["tracks"])
    assert len(draft["materials"]["texts"]) == 3
