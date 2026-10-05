---
name: make-reel
description: Edit a vlog/storytelling Instagram reel from a folder of B-roll clips into a CapCut draft. Use when the user asks to make, edit or cut a reel/video/vlog from their clips (weekend, night out, travel, life abroad, activities).
---

# Make a reel

You are the editor. The user gives you a folder of raw B-roll (no talking to camera)
and you turn it into a fast, punchy, story-driven vertical reel. The output is a CapCut
desktop draft that the user opens, polishes and exports, plus an Instagram caption.

## 1. Gather

Ask only what you can't infer. Usually just:
- the clips folder (a Windows path like `C:\Users\me\Videos\lisbon-weekend`)
- what the reel is about, in a sentence ("my first weekend in Lisbon", "girls night out")
- a style, if they have one in mind. Otherwise pick one (see step 3).

If the folder holds an `.mp3`/`.m4a`/`.wav`, that's the music. Otherwise the reel is cut
to a fixed 120 BPM grid and the user adds a trending sound in CapCut.

## 2. Watch the footage

```
python -m reel scan "<folder>"
```

This writes `<folder>/_reel/clips.json` (length, orientation, capture time, GPS if
present) and one contact sheet per clip in `<folder>/_reel/sheets/`. Each sheet is a 3×2
grid of frames evenly spaced through the clip; `sheet_times` in clips.json gives the
timestamp of each frame (left to right, top row first).

**Read every contact sheet image.** For each clip, note what it shows, the best moment
(which frame), whether there's movement, people, food, landmarks, signage, light (day,
golden hour, night), and how strong it is visually. That's your shot log.

## 3. Write the story

Think like a vlogger, not a slideshow. A good reel is a tiny story with a feeling:

- **Hook (first 1–2 s)**: the strongest, most intriguing shot plus a hook line that makes
  people stay. It doesn't have to be chronologically first. Hook patterns that work:
  - POV: "POV: you moved to Lisbon and this is a normal Saturday"
  - Contrast/expectation: "I almost stayed home tonight…"
  - Curiosity: "the best €3 I've spent in Portugal"
  - Identity/relatable: "things nobody tells you about living abroad"
  - Day framing: "spend a Saturday with me in Porto"
- **Arc**: setup → build → peak → landing. Usually chronological after the hook
  (morning → afternoon → night). Group shots into mini-scenes (café, walk, beach, dinner,
  bar) with 2–4 shots each.
- **Rhythm**: vary shot lengths. Quick 1–2 beat cuts for movement and energy, a longer
  4–8 beat hold on a beautiful or emotional shot (sunset, view, friends laughing) so the
  viewer can breathe. Put the peak shot on a longer hold near the end.
- **Text as narration**: since there's no voice, on-screen text tells the story.
  - Scene labels are short, lowercase or small-caps diary notes, max ~6 words:
    "saturday 10am ☕", "first time trying sardines", "SAT · 22:00 · BAIRRO ALTO".
  - The travel style suits time/place stamps. Other styles suit casual diary lines.
  - Don't label every shot. Label the start of each mini-scene (every 2–4 shots).
  - Use at most one emoji per label.
- **Landing**: an outro line that invites a save, share or follow, tied to the story:
  "save this for your Lisbon trip", "which one would you do first?", "part 2?".
- **Length**: 12–25 s for punchy/hype/night-out (about 24–48 beats at 120 BPM), up to
  ~30 s for travel/golden. Shorter is better than padded. Leave weak shots out.

Pick the style from the mood (`python -m reel styles` lists them):
| style | use for |
|---|---|
| `punchy` (default) | weekend recaps, day-in-my-life, activities |
| `hype` | parties, festivals, concerts, sports |
| `night-out` | bars, clubs, dinners with friends, city lights |
| `travel` | trips, exploring a new city, life-abroad moments |
| `golden` | cozy weekends, brunch, sunsets, slow Sundays |

## 4. Write the plan

Save it as `<folder>/_reel/plan.json`:

```json
{
  "title": "Lisbon weekend 1",
  "style": "travel",
  "music": "song.mp3",
  "music_start": "auto",
  "hook": "POV: your first weekend living in Lisbon",
  "hook_beats": 4,
  "scenes": [
    {"clip": "IMG_2041.MOV", "in": 3.5, "beats": 2, "emphasis": true, "note": "tram passing, best frame 3"},
    {"clip": "IMG_2033.MOV", "in": 0.0, "beats": 2, "text": "SAT · 10:00 · BAIXA", "note": "coffee pour"},
    {"clip": "IMG_2034.JPG", "beats": 1},
    {"clip": "IMG_2050.MOV", "in": 12.0, "beats": 2, "speed": 2.0, "note": "walking timelapse"},
    {"clip": "IMG_2077.MOV", "in": 1.0, "beats": 8, "speed": 0.5, "note": "sunset hold, slow-mo"}
  ],
  "outro": "save this for your Lisbon trip ✈️",
  "caption": "first weekend as a Lisbon local 🇵🇹 still can't believe this is my life now",
  "hashtags": ["lisbon", "expatlife", "movingabroad", "weekendvlog", "lisboa"]
}
```

Scene fields:
- `clip` (required): file name exactly as in clips.json.
- `in`: seconds into the clip where the shot starts. Aim at the best moment from the
  contact sheet (`sheet_times`). The tool pulls it back automatically if the clip is too short.
- `beats`: shot length in beats (1 beat ≈ 0.5 s at 120 BPM). Default comes from the style.
- `speed`: 2.0 for walking/driving/timelapse energy, 0.5 for slow-mo on beautiful moments.
  If a clip is too short for its beats, the tool slows it down and prints a warning.
- `text`: an on-screen label starting at this shot.
- `emphasis`: true for 2–4 standout shots (the hook shot, the peak). They get a zoom-in
  intro animation (and a beat effect in hype/night-out).
- `frame`: `"auto"` (default: portrait fills the frame, landscape sits on a blurred
  background), `"fill"` (crop landscape to fill; good for scenery with a centered subject)
  or `"fit"`.
- `transition`: a transition into the next shot (`Whip_Tear`, `Snap_Zoom`, `Flash`,
  `Swipe_Left`, `Light_Leaks`, ...) or `"none"` for a hard cut. When unset, the style decides.
- `keep_audio`: true to keep the clip's own sound under the music (laughter, crowd, waves).
- `note`: your reminder of what's in the shot. Ignored by the tool.

Top-level fields: `music` is a file name in the folder or null. `music_start` is
`"auto"` (starts at the most energetic part of the song) or a number of seconds.
`bpm` is used only when there's no music (default 120). `caption` and `hashtags` hold
the Instagram caption: 3–5 specific hashtags beat 30 generic ones.

The same clip can appear more than once with different `in` points; that's normal for
B-roll. Avoid repeating the exact same moment.

## 5. Check, then build

```
python -m reel timeline "<folder>\_reel\plan.json"   # resolved cut list, warnings
python -m reel preview  "<folder>\_reel\plan.json"   # optional quick MP4 (cuts + music only)
python -m reel build    "<folder>\_reel\plan.json"   # writes the CapCut draft + caption.txt
```

Fix any warnings that matter (for example, a 3 s clip stretched across 8 beats looks
sluggish; give it fewer beats). `build` finds CapCut's drafts folder automatically on
Windows/Mac. Otherwise pass `--drafts "<path>"`. Re-running build overwrites the draft
with the same title.

## 6. Hand off

Tell the user:
- the draft name to open in CapCut (restart CapCut if it doesn't show up)
- the story in 2–3 lines (hook → arc → ending), so they can ask for changes
- the caption and hashtags, ready to paste
- what to check in CapCut: text positions and the music, and swapping in a trending
  sound if they used no music file

For revisions ("make it shorter", "start with the sunset", "more chaotic"), edit plan.json
and run build again. Don't start over.
