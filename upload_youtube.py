#!/usr/bin/env python3
"""
SweetSoul Stories - YouTube uploader (CLI).

Reads reels recorded in manifest.json (newest first) and uploads the ones that
have not been uploaded yet via the YouTube Data API v3 (OAuth2). Credentials
come from environment variables (GitHub Secrets) - see modules/youtube.py.

Usage
-----
  # One-time interactive authorization to mint a token (run locally):
  python upload_youtube.py --authorize

  # Upload the most recent un-uploaded reel(s):
  python upload_youtube.py --limit 1

  # Upload as unlisted instead of public:
  python upload_youtube.py --limit 1 --privacy unlisted
"""

import argparse
import json
import logging
import os
import sys

from modules.config import BASE_DIR, get_cfg, setup_logging
from modules import youtube

log = logging.getLogger("sweetsoul.upload.youtube")

MANIFEST_PATH = os.path.join(str(BASE_DIR), "manifest.json")


def _load_manifest():
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("reels"), list):
            return data
    except Exception as exc:
        log.error("Could not read manifest (%s).", exc)
    return {"reels": []}


def _save_manifest(manifest):
    try:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        log.error("Could not write manifest (%s).", exc)


def _build_title(entry):
    """Cute, USA-friendly Shorts title with a couple of hashtags."""
    base = entry.get("title") or "A SweetSoul Story"
    # Keep it short and add #Shorts so YouTube treats it as a Short.
    title = f"{base} | Cute & Wholesome #shorts #cute"
    return title[:100]


def _tags(entry):
    kw = entry.get("keywords") or []
    return list(kw)


def upload_pending(limit=1, privacy=None):
    manifest = _load_manifest()
    reels = manifest.get("reels", [])
    if not reels:
        log.warning("No reels in manifest; nothing to upload. Run generate.py first.")
        return []

    privacy = privacy or get_cfg("youtube.privacy_status", "public")
    # Newest first.
    pending = [r for r in reversed(reels) if not r.get("uploaded_youtube")]
    if not pending:
        log.info("All reels already uploaded to YouTube.")
        return []

    uploaded = []
    for entry in pending[: max(1, int(limit))]:
        video_rel = entry.get("video_path")
        video_path = os.path.join(str(BASE_DIR), video_rel) if video_rel else None
        if not video_path or not os.path.exists(video_path):
            log.error("Video file missing for '%s' (%s); skipping.", entry.get("title"), video_path)
            continue
        vid = youtube.upload_video(
            video_path=video_path,
            title=_build_title(entry),
            description=entry.get("description", ""),
            tags=_tags(entry),
            privacy=privacy,
        )
        if vid:
            entry["uploaded_youtube"] = True
            entry["youtube_id"] = vid
            uploaded.append(entry)
            _save_manifest(manifest)
        else:
            log.error("Upload failed for '%s'.", entry.get("title"))

    log.info("Uploaded %d reel(s) to YouTube.", len(uploaded))
    return uploaded


def main(argv=None):
    parser = argparse.ArgumentParser(description="Upload SweetSoul reels to YouTube.")
    parser.add_argument("--authorize", action="store_true", help="Run one-time OAuth authorization.")
    parser.add_argument("--limit", type=int, default=1, help="Max reels to upload this run.")
    parser.add_argument("--privacy", type=str, default=None,
                        choices=["public", "unlisted", "private"],
                        help="Privacy status (default from config.json: public).")
    args = parser.parse_args(argv)

    setup_logging()

    if args.authorize:
        path = youtube.authorize()
        return 0 if path else 1

    upload_pending(limit=args.limit, privacy=args.privacy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
