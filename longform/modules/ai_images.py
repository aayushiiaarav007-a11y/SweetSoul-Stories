"""
Free AI scene-image generation for MoralTales Longform.

Uses Pollinations.ai (FREE, no API key) to turn each story SCENE into a
children's-storybook illustration that actually MATCHES the story's characters
and setting (a child, an old man, an animal, a village, etc.). These images are
then Ken-Burns animated as the video background, so the visuals follow the
story instead of being generic stock clips.

Fully defensive:
  * No key needed. On ANY failure (service down, timeout, bad bytes) it returns
    whatever it managed to fetch; if it returns nothing, the composer falls back
    to Pexels footage and then a gradient. The video never fails because of this.
  * Old generated images are cleared each run so every episode looks fresh.

stdlib + requests only.
"""

import logging
import os
import random
import time
import urllib.parse

from .config import IMAGES_DIR, get_cfg

log = logging.getLogger("moraltales.aiimages")

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"


def _requests():
    try:
        import requests

        return requests
    except Exception as exc:  # pragma: no cover
        log.error("'requests' is required for AI images (%s).", exc)
        return None


def _looks_like_image(path):
    try:
        if os.path.getsize(path) < 3000:
            return False
        with open(path, "rb") as fh:
            head = fh.read(12)
        # JPEG (FFD8), PNG (89504E47), WEBP ('RIFF'....'WEBP')
        return (
            head[:2] == b"\xff\xd8"
            or head[:8] == b"\x89PNG\r\n\x1a\n"
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
        )
    except Exception:
        return False


def _clear_old_images():
    try:
        for fname in os.listdir(IMAGES_DIR):
            if fname.startswith("scene_") and fname.lower().endswith((".jpg", ".png", ".webp")):
                try:
                    os.remove(os.path.join(IMAGES_DIR, fname))
                except Exception:
                    pass
    except Exception:
        pass


def _fetch_one(requests, prompt, dest, width, height, seed):
    full = (
        f"{get_cfg('ai_images.style', 'soft warm childrens storybook illustration, gentle cartoon style, wholesome, no text, no words')}, "
        f"{prompt}"
    )
    url = POLLINATIONS_URL + urllib.parse.quote(full)
    params = {"width": width, "height": height, "nologo": "true", "seed": seed, "model": get_cfg("ai_images.model", "flux")}
    for attempt in range(1, 3):
        try:
            with requests.get(url, params=params, timeout=90, stream=True) as resp:
                if resp.status_code != 200:
                    log.warning("Pollinations HTTP %s (attempt %d) for %r", resp.status_code, attempt, prompt[:50])
                    time.sleep(2 * attempt)
                    continue
                tmp = dest + ".part"
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        if chunk:
                            fh.write(chunk)
                os.replace(tmp, dest)
            if _looks_like_image(dest):
                return True
            try:
                os.remove(dest)
            except Exception:
                pass
        except Exception as exc:
            log.warning("Pollinations error attempt %d (%s).", attempt, exc)
            time.sleep(2 * attempt)
    return False


def generate_scene_images(scene_prompts, max_images=None):
    """Generate one storybook image per scene prompt. Returns a list of local
    image paths in scene order (may be shorter than the input on partial
    failure, or empty if the service is unavailable)."""
    if not get_cfg("ai_images.enabled", True):
        return []
    scene_prompts = [s for s in (scene_prompts or []) if s and str(s).strip()]
    if not scene_prompts:
        return []

    requests = _requests()
    if requests is None:
        return []

    if max_images is None:
        max_images = int(get_cfg("ai_images.max_images", 14))
    scene_prompts = scene_prompts[:max_images]

    width = int(get_cfg("ai_images.width", 1920))
    height = int(get_cfg("ai_images.height", 1080))
    # A single base seed per video keeps the art style consistent across scenes.
    base_seed = random.randint(1, 9_999_999)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    _clear_old_images()

    paths = []
    for i, prompt in enumerate(scene_prompts):
        dest = os.path.join(str(IMAGES_DIR), "scene_%02d.jpg" % i)
        if _fetch_one(requests, str(prompt).strip(), dest, width, height, base_seed + i):
            paths.append(dest)
            log.info("AI image %d/%d ready.", len(paths), len(scene_prompts))
        else:
            log.warning("AI image %d failed; continuing.", i + 1)
    if paths:
        log.info("Generated %d AI scene image(s).", len(paths))
    else:
        log.warning("No AI images generated; composer will use stock footage instead.")
    return paths
