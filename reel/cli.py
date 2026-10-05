"""Command line: python -m reel <command> ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import beats as beatlib
from .media import AUDIO_EXTS, WORK_DIR, require_ffmpeg, scan
from .plan import TEXT_MODES, US, build_timeline, clips_folder_for, load_plan
from .styles import STYLES


def cmd_scan(args) -> None:
    folder = Path(args.folder)
    if not folder.is_dir():
        raise SystemExit(f"Not a folder: {folder}")
    print(f"Scanning {folder} ...")
    data = scan(folder)
    print(f"Found {len(data['clips'])} clips and {len(data['music'])} music file(s).")
    for c in data["clips"]:
        length = f"{c['duration']:.1f}s" if c["kind"] == "video" else "photo"
        print(f"  {c['file']:<32} {length:>7}  {c['orientation']:<9} {c['created'] or ''}")
    for m in data["music"]:
        print(f"  music: {m}")
    print(f"\nContact sheets: {Path(data['folder']) / WORK_DIR / 'sheets'}")
    print(f"Clip index:     {Path(data['folder']) / WORK_DIR / 'clips.json'}")


def cmd_beats(args) -> None:
    require_ffmpeg()
    grid = beatlib.analyze(Path(args.audio))
    print(f"Tempo: {grid.bpm:.1f} BPM, {len(grid.beats)} beats, beat length {grid.period:.3f}s")
    for n in (16, 24, 32, 48):
        i = beatlib.pick_start_beat(grid, n)
        print(f"  best start for a {n}-beat reel ({n * grid.period:.1f}s): {grid.beats[i]:.2f}s into the song")


def cmd_styles(_args) -> None:
    for s in STYLES.values():
        print(f"{s.name:<10} {s.description}")


def _timeline(args):
    plan_path = Path(args.plan)
    plan = load_plan(plan_path)
    folder = clips_folder_for(plan_path, plan)
    if args.style:
        plan["style"] = args.style
    if args.text:
        plan["text_mode"] = args.text
    tl = build_timeline(plan, folder)
    print(f"'{tl.title}': {len(tl.shots)} shots, {tl.duration / US:.1f}s at {tl.bpm:.0f} BPM, "
          f"style '{tl.style.name}', text '{tl.text_mode}'"
          + (f", music from {tl.music_offset / US:.1f}s" if tl.music else ", no music (add a sound in CapCut)"))
    for w in tl.warnings:
        print(f"  ! {w}")
    if tl.unused:
        print(f"  Not used ({len(tl.unused)}):")
        for name in tl.unused:
            reason = tl.skipped.get(name)
            print(f"    - {name}" + (f": {reason}" if reason else ""))
    return tl, folder


def cmd_build(args) -> None:
    from .capcut import default_drafts_folder, write_draft  # imports pycapcut

    require_ffmpeg()
    tl, folder = _timeline(args)
    drafts = Path(args.drafts) if args.drafts else default_drafts_folder()
    if drafts is None:
        raise SystemExit("Couldn't find CapCut's drafts folder. Open CapCut desktop → Settings → "
                         "'Drafts location', then pass it with --drafts \"<path>\" "
                         "or set the CAPCUT_DRAFTS environment variable.")
    path = write_draft(tl, drafts, args.name)
    caption_file = folder / WORK_DIR / "caption.txt"
    caption_file.write_text(tl.caption_text + "\n", encoding="utf-8")
    print(f"\nCapCut draft written: {path}")
    print("Open CapCut desktop. If the draft doesn't appear, open and close any project (or restart CapCut).")
    if tl.caption_text:
        print(f"\nInstagram caption (also saved to {caption_file}):\n\n{tl.caption_text}\n")


def cmd_preview(args) -> None:
    from .preview import render_preview

    require_ffmpeg()
    tl, folder = _timeline(args)
    out = Path(args.out) if args.out else folder / WORK_DIR / "preview.mp4"
    render_preview(tl, out)
    print(f"Preview written: {out}")


def cmd_timeline(args) -> None:
    tl, _ = _timeline(args)
    rows = [{"clip": s.clip, "start": round(s.start / US, 3), "duration": round(s.duration / US, 3),
             "uses": [round(s.source_in / US, 2), round((s.source_in + s.duration * s.speed) / US, 2)]
             if s.kind == "video" else "photo",
             "speed": s.speed, "transition": s.transition}
            for s in tl.shots]
    caps = [{"role": c.role, "text": c.text, "start": round(c.start / US, 3), "duration": round(c.duration / US, 3)}
            for c in tl.captions]
    print(json.dumps({"shots": rows, "captions": caps}, indent=2, ensure_ascii=False))


def main(argv=None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emoji in captions on Windows terminals
    p = argparse.ArgumentParser(prog="python -m reel", description="Vlog-style reel editor that writes CapCut drafts.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="probe clips and make contact sheets for Claude")
    s.add_argument("folder")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("beats", help="detect tempo and the best start point of a song")
    s.add_argument("audio")
    s.set_defaults(func=cmd_beats)

    s = sub.add_parser("styles", help="list style presets")
    s.set_defaults(func=cmd_styles)

    for name, func, helptext in (("build", cmd_build, "write the CapCut draft from a plan"),
                                 ("preview", cmd_preview, "render a quick MP4 preview (cuts + music)"),
                                 ("timeline", cmd_timeline, "print the resolved, beat-aligned timeline")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("plan", help="path to plan.json (usually <clips>/_reel/plan.json)")
        s.add_argument("--style", choices=list(STYLES), help="override the plan's style")
        s.add_argument("--text", choices=list(TEXT_MODES),
                       help="override on-screen text: none, hook (opening/closing line only) or story (+ scene labels)")
        if name == "build":
            s.add_argument("--drafts", help="CapCut drafts folder (auto-detected on Windows/Mac)")
            s.add_argument("--name", help="draft name (defaults to the plan title)")
        if name == "preview":
            s.add_argument("--out", help="output .mp4 path")
        s.set_defaults(func=func)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, RuntimeError) as err:
        raise SystemExit(f"Error: {err}")


if __name__ == "__main__":
    main()
