# Reel Editor 🎬

Your personal vlog editor. Drop your weekend, night-out or travel clips into a folder and
ask Claude to make a reel. Claude watches the footage, writes a little story (hook, scenes,
on-screen text, ending, caption and hashtags), and builds a **beat-synced CapCut draft**
that you open, polish and export.

Inspired by The Startup Mom's *Reels Editing Engine* (Claude + CapCut). The difference is
style: this one is made for **storytelling vlogs** (your weekends, going out, life in a new
country, travel, activities), cut from B-roll with music and text instead of talking-head footage.

## How it works

```
your clips ──► scan (contact sheets) ──► Claude watches & writes the story (plan.json)
           ──► beats detected in your song ──► CapCut draft + Instagram caption
```

What you get in CapCut:
- 9:16 vertical timeline with cuts landing on the beat of your song
- a hook line on screen for the first seconds, diary labels per scene, and an outro line
- transitions, zoom-in emphasis on the best shots, a slow push-in on every clip
- a colour filter and effects that match the chosen style
- landscape clips placed on a blurred background, portrait clips filling the frame
- `caption.txt` with your Instagram caption and hashtags

### Styles

| style | feel | best for |
|---|---|---|
| `punchy` (default) | 2-beat cuts, snap/whip transitions, bold text | weekend recaps, day in my life, activities |
| `hype` | 1-beat cuts, flashes, beat effect | parties, festivals, concerts, sports |
| `night-out` | hype pacing, neon filter, glowing text | bars, clubs, dinners, city lights |
| `travel` | whip pans, warm grade, typewriter stamps (`SAT · 10:00 · ALFAMA`) | trips, exploring, life abroad |
| `golden` | a bit slower, light leaks, warm grade | cozy weekends, brunch, sunsets |

Ask for one ("make it night-out style") or let Claude pick from the footage.

## One-time setup (Windows)

1. **CapCut desktop**: install it from capcut.com and open it once. Drafts can only be
   generated for the desktop app, not the phone app. You can still export the finished
   reel and send it to your phone.
2. **Python 3.10+**: install it from python.org and tick *"Add python.exe to PATH"*.
3. **FFmpeg**: in PowerShell, run `winget install Gyan.FFmpeg`, then open a new terminal.
4. **Claude Code**: install the Claude desktop app (Code tab) or Claude Code in the terminal.
5. Get this project and install its dependencies:
   ```powershell
   git clone https://github.com/stanculescumadalina-svg/Reel-editor.git
   cd Reel-editor
   pip install -r requirements.txt
   ```

The CapCut drafts folder is found automatically
(`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`). If you changed it
in CapCut (Settings → Drafts location), set it once with:
`setx CAPCUT_DRAFTS "D:\path\to\your\drafts"`.

## Making a reel

1. Put the clips for one reel in a folder. Add a song (`.mp3`/`.m4a`) if you want cuts on
   its beat. Without one, the reel is cut at 120 BPM and you add a trending sound in CapCut.
2. Open Claude Code in the `reel-editor` folder and say something like:
   > Make a reel from `C:\Users\me\Videos\lisbon-weekend`. It's my first weekend living in Lisbon.
3. Claude scans, watches and writes the plan, then builds the draft. Open CapCut. You'll see
   the new draft (restart CapCut if it doesn't appear).
4. Tweak anything in CapCut, export, and post with the caption Claude wrote.

Want changes? Just say "shorter", "start with the sunset", "more chaotic", or "different
hook". Claude edits the plan and rebuilds the draft.

**Keep the clips where they are.** The CapCut draft links to the original files.

### Commands (what Claude runs for you)

```
python -m reel scan <folder>          # probe clips + contact sheets → <folder>\_reel\
python -m reel styles                 # list style presets
python -m reel beats <song.mp3>       # tempo + best start point
python -m reel timeline <plan.json>   # show the resolved, beat-aligned cut list
python -m reel preview <plan.json>    # quick MP4 preview (cuts + music only)
python -m reel build <plan.json>      # write the CapCut draft + caption.txt
```

The plan format is documented in `.claude/skills/make-reel/SKILL.md`, with an example in
`examples/plan.example.json`.

## Notes and limits

- Built on [pyCapCut](https://github.com/GuanYixuan/pyCapCut). The fonts, transitions,
  filters and effects used are CapCut's free ones.
- CapCut changes its draft format from time to time. If a new CapCut version won't open a
  draft, update pyCapCut (`pip install -U pycapcut`) and tell Claude.
- Claude reads still frames, not sound, so it can't judge the song. It just finds the
  beats and the most energetic part automatically.

## Development

```
pip install -r requirements.txt pytest
python -m pytest -q
```
