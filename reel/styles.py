"""Editing style presets. Every reel picks one; scenes can still override details.

Effect, transition and animation names are pyCapCut enum member names
(CapCut's own free effects). Some animations only exist under their Chinese
CapCut name; the English meaning is noted next to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Style:
    name: str
    description: str
    beats_per_cut: int                   # default scene length when a scene doesn't say
    transitions: tuple[str, ...]         # rotated through on transition points
    transition_every: int                # put a transition on every Nth cut (0 = never); the rest are hard cuts
    emphasis_intro: str                  # video intro animation for scenes marked "emphasis"
    emphasis_effect: str | None          # scene effect over emphasis scenes
    filter: str | None                   # colour filter over the whole reel
    filter_intensity: float
    punch_zoom: float                    # slow zoom-in over each clip (1.0 = none, 1.08 = subtle push)
    hook_font: str
    label_font: str
    hook_size: float
    label_size: float
    text_color: tuple[float, float, float]
    text_intro: str
    text_outro: str
    label_box: str | None = None         # "#RRGGBB" background box behind labels (None = outline only)
    tags: tuple[str, ...] = field(default_factory=tuple)


STYLES: dict[str, Style] = {s.name: s for s in [
    Style(
        name="punchy",
        description="Default. Two-beat cuts, a snap/whip transition every few cuts, bold white text with an outline. "
                    "Works for weekend recaps, day-in-my-life and activity reels.",
        beats_per_cut=2,
        transitions=("Snap_Zoom", "Whip_Tear", "Zoom_Transition", "Swipe_Left"),
        transition_every=4,
        emphasis_intro="动感放大",          # "dynamic zoom in"
        emphasis_effect=None,
        filter=None,
        filter_intensity=0,
        punch_zoom=1.06,
        hook_font="Anton",
        label_font="Poppins_Bold",
        hook_size=13.0,
        label_size=8.0,
        text_color=(1.0, 1.0, 1.0),
        text_intro="向上弹入",              # "bounce up"
        text_outro="渐隐",                  # "fade out"
        tags=("weekend", "day in my life", "activities"),
    ),
    Style(
        name="hype",
        description="One-beat cuts, flash and shake transitions, beat-shot effect on emphasis scenes. "
                    "For parties, festivals, concerts, sports: anything high-energy.",
        beats_per_cut=1,
        transitions=("Flash", "Zoom_Shake_2", "White_Flash", "Jerky_Camera"),
        transition_every=3,
        emphasis_intro="上下抖动",          # "up-down shake"
        emphasis_effect="Beat_Shots",
        filter=None,
        filter_intensity=0,
        punch_zoom=1.1,
        hook_font="BebasNeue",
        label_font="BebasNeue",
        hook_size=15.0,
        label_size=10.0,
        text_color=(1.0, 1.0, 1.0),
        text_intro="故障弹跳",              # "glitch bounce"
        text_outro="故障",                  # "glitch"
        tags=("party", "festival", "concert", "sports"),
    ),
    Style(
        name="night-out",
        description="Hype pacing with a neon party look: Party Tonight filter, flickery shots, glowing text. "
                    "For bars, clubs, dinners with friends, city lights.",
        beats_per_cut=1,
        transitions=("Neon", "Flash", "Lumin_Flash", "Zoom_Shake_2"),
        transition_every=3,
        emphasis_intro="动感放大",
        emphasis_effect="Flickery_Shots",
        filter="Party_Tonight",
        filter_intensity=70,
        punch_zoom=1.08,
        hook_font="Shrikhand",
        label_font="Poppins_Bold",
        hook_size=13.0,
        label_size=8.0,
        text_color=(1.0, 0.85, 0.98),
        text_intro="辉光入场",              # "glow in"
        text_outro="辉光渐隐",              # "glow fade out"
        tags=("night out", "bar", "club", "dinner", "city lights"),
    ),
    Style(
        name="travel",
        description="Two-beat cuts with whip pans, a warm tropical grade and typewriter location stamps "
                    "('SAT · 10:00 · ALFAMA'). For trips, new-city exploring, life-abroad moments.",
        beats_per_cut=2,
        transitions=("Whip_Tear", "Swipe_Left", "Light_Leaks", "Slide_Drop"),
        transition_every=3,
        emphasis_intro="向右甩入",          # "swing in from the left"
        emphasis_effect=None,
        filter="Tropical_Velvet",
        filter_intensity=45,
        punch_zoom=1.06,
        hook_font="Anton",
        label_font="Typewriter",
        hook_size=13.0,
        label_size=7.0,
        text_color=(1.0, 1.0, 1.0),
        text_intro="打字机",                # "typewriter"
        text_outro="渐隐",
        label_box="#000000",
        tags=("travel", "trip", "new country", "exploring"),
    ),
    Style(
        name="golden",
        description="Still upbeat but warmer and a touch slower (3-beat cuts), light leaks and soft grain. "
                    "For cozy weekends, brunches, sunsets, slow Sundays.",
        beats_per_cut=3,
        transitions=("Light_Leaks", "Film_Burn", "Swipe_Left"),
        transition_every=3,
        emphasis_intro="模糊渐显",          # "blur in"
        emphasis_effect=None,
        filter="Peach_Fuzz",
        filter_intensity=55,
        punch_zoom=1.05,
        hook_font="PlayfairDisplay_Italic",
        label_font="PlayfairDisplay_Italic",
        hook_size=12.0,
        label_size=8.0,
        text_color=(1.0, 0.97, 0.9),
        text_intro="渐显",                  # "fade in"
        text_outro="渐隐",
        tags=("cozy", "brunch", "sunset", "sunday"),
    ),
]}

DEFAULT_STYLE = "punchy"


def get_style(name: str | None) -> Style:
    key = (name or DEFAULT_STYLE).lower()
    if key not in STYLES:
        raise ValueError(f"Unknown style '{name}'. Choose one of: {', '.join(STYLES)}")
    return STYLES[key]
