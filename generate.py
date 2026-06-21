#!/usr/bin/env python3
"""
SweetSoul Stories - reel generation pipeline (CLI).

End-to-end, defensive pipeline that, for each reel:
  1. Generates a heartwarming ~150-word script (Gemini -> quotes.json fallback).
  2. Synthesizes a warm USA female voiceover (edge-tts -> gTTS fallback).
  3. Builds a cinematic 1080x1920 vertical reel with a scroll-stopping 5s hook,
     real Pexels footage (photo/Picsum/gradient fallbacks), and timing-based
     animated captions.
  4. Records everything in a manifest.json so the uploader can post later.

Usage examples
--------------
  # Generate ONE reel (the default the GitHub Actions schedule uses):
  python generate.py --days 1 --per-day 1

  # Generate a small batch:
  python generate.py --days 1 --per-day 3

  # Generate around a specific topic idea:
  python generate.py --topic "rescue kitten finds a forever home"

The total number of reels produced is days * per_day (optionally capped by
--limit). Heavy media libraries are imported lazily inside the modules so that
`python generate.py --help` works even before dependencies are installed.
"""

import argparse
import datetime as _dt
import json
import logging
import os
import sys

from modules.config import OUTPUT_DIR, BASE_DIR, setup_logging
from modules import gemini_script
from modules import tts
from modules import video_composer

log = logging.getLogger("sweetsoul.generate")

MANIFEST_PATH = os.path.join(str(BASE_DIR), "manifest.json")


def _slugify(text, max_len=40):
    """Make a filesystem-safe slug from a title."""
    keep = []
    for ch in (text or "").lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in (" ", "-", "_"):
            keep.append("-")
    slug = "".join(keep).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug or "sweetsoul")[:max_len]


def _load_manifest():
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("reels"), list):
            return data
    except Exception:
        pass
    return {"reels": []}


def _save_manifest(manifest):
    try:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        log.info("Manifest updated: %s (%d reel(s)).", MANIFEST_PATH, len(manifest["reels"]))
    except Exception as exc:
        log.error("Could not write manifest (%s).", exc)


def _build_description(script):
    """Compose a wholesome, USA-friendly description from the script."""
    intro = script.text.strip()
    return (
        f"{intro}\n\n"
        "Thanks for watching SweetSoul Stories - your daily dose of joy. "
        "Follow for more heartwarming pets and babies every day!"
    )


def generate_one(topic=None, index=0):
    """Generate a single reel. Returns a manifest entry dict or None."""
    # 1) Script
    script = gemini_script.generate_script(topic)
    log.info("Script: '%s' (%d words). Hook: %r", script.title, script.word_count, script.hook)

    stamp = _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(script.title)
    base_name = f"{stamp}-{index:02d}-{slug}"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    voice_path = os.path.join(str(OUTPUT_DIR), base_name + ".mp3")
    video_path = os.path.join(str(OUTPUT_DIR), base_name + ".mp4")

    # 2) Voiceover
    if tts.synthesize(script.text, voice_path) is None:
        log.error("Voiceover synthesis failed; skipping this reel.")
        return None

    # 3) Compose video
    try:
        out = video_composer.compose_video(
            voice_path=voice_path,
            text=script.text,
            keywords=script.keywords,
            hook_text=script.hook,
            out_path=video_path,
        )
    except Exception as exc:
        log.exception("Video composition failed (%s).", exc)
        return None

    entry = {
        "title": script.title,
        "hook": script.hook,
        "text": script.text,
        "keywords": list(script.keywords),
        "description": _build_description(script),
        "video_path": os.path.relpath(out, str(BASE_DIR)),
        "voice_path": os.path.relpath(voice_path, str(BASE_DIR)),
        "created_utc": stamp,
        "uploaded_youtube": False,
        "youtube_id": None,
        "uploaded_instagram": False,
    }
    return entry


def run(days=1, per_day=1, limit=None, topic=None):
    """Generate days * per_day reels (optionally capped by limit)."""
    total = max(1, int(days)) * max(1, int(per_day))
    if limit is not None:
        total = min(total, max(1, int(limit)))
    log.info("Generating %d reel(s) (days=%s, per_day=%s, limit=%s).", total, days, per_day, limit)

    manifest = _load_manifest()
    produced = []
    for i in range(total):
        log.info("=== Reel %d/%d ===", i + 1, total)
        entry = generate_one(topic=topic, index=i)
        if entry:
            manifest["reels"].append(entry)
            produced.append(entry)
            _save_manifest(manifest)  # persist after each success
        else:
            log.warning("Reel %d/%d was not produced.", i + 1, total)

    log.info("Done. Produced %d/%d reel(s).", len(produced), total)
    return produced


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate SweetSoul Stories reels.")
    parser.add_argument("--days", type=int, default=1, help="Number of days to generate for.")
    parser.add_argument("--per-day", type=int, default=1, dest="per_day", help="Reels per day.")
    parser.add_argument("--limit", type=int, default=None, help="Hard cap on total reels.")
    parser.add_argument("--topic", type=str, default=None, help="Optional story topic hint.")
    args = parser.parse_args(argv)

    setup_logging()
    produced = run(days=args.days, per_day=args.per_day, limit=args.limit, topic=args.topic)
    if not produced:
        log.error("No reels were produced.")
        return 1
    print("\nGenerated reels:")
    for e in produced:
        print(f"  - {e['title']}  ->  {e['video_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
