"""
Robust Pexels VIDEO fetching for SweetSoul Stories.

Design goals (loud + defensive):
  * Detect a missing / blank / placeholder PEXELS_API_KEY early and log a clear
    error instead of failing silently.
  * On non-200 responses, log status + reason + a truncated body.
      - 401 / 403 => key is invalid: stop retrying.
      - 429       => rate limited: back off.
  * Multi-pass search to maximise the chance of getting portrait footage:
      (a) themed keywords WITH portrait orientation,
      (b) themed keywords with NO orientation filter,
      (c) configured default_keywords with NO orientation filter.
  * Cache downloads on disk and validate file magic bytes.

stdlib + requests only.
"""

import logging
import os
import time

from .config import CACHE_DIR, CLIPS_DIR, get_cfg, get_env

log = logging.getLogger("sweetsoul.pexels.video")

PEXELS_VIDEO_SEARCH = "https://api.pexels.com/videos/search"

# Video container magic bytes we accept (mp4/mov family contain 'ftyp').
_MAX_BODY_LOG = 300


def _api_key():
    key = get_env("PEXELS_API_KEY")
    if not key:
        log.error(
            "PEXELS_API_KEY is missing/blank/placeholder. Pexels video will be "
            "skipped; the pipeline will fall back to photos/Picsum/gradient. "
            "Set PEXELS_API_KEY to enable real stock footage."
        )
        return None
    if len(key) < 20:
        log.warning("PEXELS_API_KEY looks unusually short - it may be invalid.")
    return key


def _requests():
    try:
        import requests

        return requests
    except Exception as exc:  # pragma: no cover - requests is a hard dep at runtime
        log.error("The 'requests' library is required (%s).", exc)
        return None


def _looks_like_video(path):
    """Validate by checking for an 'ftyp' atom near the start of the file."""
    try:
        if os.path.getsize(path) < 10000:
            return False
        with open(path, "rb") as fh:
            head = fh.read(64)
        return b"ftyp" in head or b"moov" in head or b"mdat" in head
    except Exception:
        return False


def _download(url, dest, requests):
    """Download a URL to dest with a couple of retries. Returns True/False."""
    if os.path.exists(dest) and _looks_like_video(dest):
        log.info("Using cached video: %s", os.path.basename(dest))
        return True
    for attempt in range(1, 3):
        try:
            with requests.get(url, stream=True, timeout=60) as resp:
                if resp.status_code != 200:
                    log.warning(
                        "Download failed (HTTP %s) on attempt %d for %s",
                        resp.status_code,
                        attempt,
                        url[:80],
                    )
                    time.sleep(1.5 * attempt)
                    continue
                tmp = dest + ".part"
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        if chunk:
                            fh.write(chunk)
                os.replace(tmp, dest)
            if _looks_like_video(dest):
                return True
            log.warning("Downloaded file failed validation: %s", dest)
            try:
                os.remove(dest)
            except Exception:
                pass
        except Exception as exc:
            log.warning("Download error on attempt %d (%s).", attempt, exc)
            time.sleep(1.5 * attempt)
    return False


def _pick_portrait_file(video_files):
    """Choose the best portrait-ish rendition from a Pexels video entry."""
    best = None
    best_score = -1
    for vf in video_files:
        w = vf.get("width") or 0
        h = vf.get("height") or 0
        link = vf.get("link")
        if not link:
            continue
        # Prefer portrait (h > w) and a height around 1920.
        portrait_bonus = 1000 if h >= w else 0
        # Penalise distance from target height 1920.
        score = portrait_bonus - abs(1920 - h)
        if score > best_score:
            best_score = score
            best = link
    return best


def _search(requests, headers, query, per_page, orientation):
    params = {"query": query, "per_page": per_page}
    if orientation:
        params["orientation"] = orientation
    try:
        resp = requests.get(PEXELS_VIDEO_SEARCH, headers=headers, params=params, timeout=30)
    except Exception as exc:
        log.warning("Pexels request error for '%s' (%s).", query, exc)
        return None, False  # (results, stop_all)

    if resp.status_code == 200:
        try:
            return resp.json().get("videos", []), False
        except Exception as exc:
            log.warning("Could not parse Pexels JSON for '%s' (%s).", query, exc)
            return [], False

    body = ""
    try:
        body = resp.text[:_MAX_BODY_LOG]
    except Exception:
        pass
    log.error(
        "Pexels video search failed: HTTP %s %s | query=%r | body=%s",
        resp.status_code,
        getattr(resp, "reason", ""),
        query,
        body,
    )
    if resp.status_code in (401, 403):
        log.error("Pexels API key invalid/forbidden (HTTP %s). Stopping retries.", resp.status_code)
        return None, True  # stop everything
    if resp.status_code == 429:
        log.warning("Pexels rate limited (429). Backing off for 3s.")
        time.sleep(3)
    return [], False


def fetch_pexels_videos(keywords, min_clips=None):
    """Return a list of local mp4 paths for portrait-ish cute footage.

    Returns an empty list if the key is missing/invalid or nothing was found,
    allowing the caller to fall back to photos / Picsum / gradient.
    """
    key = _api_key()
    if not key:
        return []
    requests = _requests()
    if requests is None:
        return []

    if min_clips is None:
        min_clips = get_cfg("pexels.min_clips", 6)
    per_page = get_cfg("pexels.per_query", 15)
    orientation = get_cfg("pexels.orientation", "portrait")
    default_keywords = get_cfg("pexels.default_keywords", [])

    headers = {"Authorization": key}
    keywords = [k for k in (keywords or []) if k] or list(default_keywords)

    os.makedirs(CLIPS_DIR, exist_ok=True)
    collected = []
    seen_ids = set()

    # Build the three search passes.
    passes = [
        ("themed + portrait", keywords, orientation),
        ("themed + any orientation", keywords, None),
        ("default keywords + any orientation", default_keywords, None),
    ]

    for label, kw_list, orient in passes:
        if len(collected) >= min_clips:
            break
        if not kw_list:
            continue
        log.info("Pexels video pass: %s", label)
        for query in kw_list:
            if len(collected) >= min_clips:
                break
            videos, stop_all = _search(requests, headers, query, per_page, orient)
            if stop_all:
                return collected  # key invalid - return whatever we have (likely [])
            for entry in videos or []:
                if len(collected) >= min_clips:
                    break
                vid_id = entry.get("id")
                if vid_id in seen_ids:
                    continue
                link = _pick_portrait_file(entry.get("video_files", []))
                if not link:
                    continue
                dest = os.path.join(CLIPS_DIR, "pexels_%s.mp4" % vid_id)
                if _download(link, dest, requests):
                    seen_ids.add(vid_id)
                    collected.append(dest)
                    log.info("Got clip %d/%d: %s", len(collected), min_clips, os.path.basename(dest))

    if not collected:
        log.warning("No Pexels videos collected after all passes.")
    else:
        log.info("Collected %d Pexels video clip(s).", len(collected))
    return collected
