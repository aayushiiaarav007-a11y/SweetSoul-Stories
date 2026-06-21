"""
Video composition for SweetSoul Stories.

Assembles a 60s vertical 1080x1920 reel:
  * Background built from a priority chain (Pexels video -> Pexels photos
    Ken-Burns -> warm animated gradient). Random/irrelevant keyless stock
    images are deliberately NOT used.
  * A subtle BRIGHT, VIVID, PUNCHY grade (gentle saturation + slight
    brightness/contrast lift; vignette nearly off; no warm haze).
  * Short crossfade transitions between background segments for smooth motion.
  * A first-5-seconds animated HOOK overlay (scale "pop" + background "punch"
    zoom + subtle flash) that stops the scroll.
  * Word-by-word style timing-based captions with a soft rounded backdrop pill
    for the rest.
  * Audio = voiceover (+ optional low-volume background music).

Heavy imports (moviepy/numpy) happen lazily inside functions so that importing
this module never hard-fails in restricted environments.
"""

# ---------------------------------------------------------------------------
# Pillow >= 10 removed Image.ANTIALIAS which moviepy 1.0.3 relies on. Re-add
# the constants at import time BEFORE moviepy is ever imported.
# ---------------------------------------------------------------------------
try:
    from PIL import Image as _PILImage
    if not hasattr(_PILImage, "ANTIALIAS"):
        _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS
    for _n in ("BILINEAR", "BICUBIC", "NEAREST", "LANCZOS", "HAMMING", "BOX"):
        if not hasattr(_PILImage, _n) and hasattr(_PILImage, "Resampling"):
            setattr(_PILImage, _n, getattr(_PILImage.Resampling, _n))
except Exception:
    pass

import logging
import os
import random

from .config import MUSIC_DIR, OUTPUT_DIR, get_cfg
from . import images as images_mod
from . import pexels_video
from . import subtitles

log = logging.getLogger("sweetsoul.video")

# Defaults (overridable via config.json).
W = get_cfg("video.width", 1080)
H = get_cfg("video.height", 1920)
FPS = get_cfg("video.fps", 30)


# ==========================================================================
# Background construction
# ==========================================================================
def _fit_cover(clip):
    """Resize+crop a clip so it covers the full WxH frame (no letterboxing)."""
    from moviepy.video.fx.all import crop

    try:
        cw, ch = clip.size
    except Exception:
        return clip.resize((W, H))

    scale = max(W / float(cw), H / float(ch))
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    clip = clip.resize((new_w, new_h))
    try:
        clip = crop(clip, width=W, height=H, x_center=new_w / 2, y_center=new_h / 2)
    except Exception:
        clip = clip.resize((W, H))
    return clip


def _concat_with_crossfade(segments, duration):
    """Concatenate clips with short crossfade transitions for a premium feel.

    Uses moviepy's crossfadein + a compose concatenation with negative padding
    so successive segments overlap by `crossfade_seconds`. Fully defensive: on
    ANY error it falls back to plain concatenation so the reel always renders.
    """
    from moviepy.editor import concatenate_videoclips

    if not segments:
        raise RuntimeError("No segments to concatenate.")

    xfade = float(get_cfg("transitions.crossfade_seconds", 0.35))

    if len(segments) > 1 and xfade > 0:
        try:
            from moviepy.video.fx.all import crossfadein

            faded = [segments[0]]
            for seg in segments[1:]:
                # Don't let the crossfade exceed the segment length.
                try:
                    seg_dur = seg.duration or xfade
                except Exception:
                    seg_dur = xfade
                this_fade = min(xfade, max(0.05, seg_dur * 0.5))
                faded.append(crossfadein(seg, this_fade))
            bg = concatenate_videoclips(faded, method="compose", padding=-xfade)
            bg = bg.set_duration(duration)
            log.info("Applied %.2fs crossfade transitions between %d segment(s).", xfade, len(segments))
            return bg
        except Exception as exc:
            log.warning("Crossfade concat failed (%s); using plain concatenation.", exc)

    bg = concatenate_videoclips(segments, method="compose").set_duration(duration)
    return bg


def _ken_burns_from_image(path, duration, zoom_end=None):
    """Create a slow Ken-Burns (pan + zoom) clip from a single image."""
    from moviepy.editor import ImageClip

    if zoom_end is None:
        zoom_end = get_cfg("video.background_zoom", 1.08)

    base = ImageClip(path).set_duration(duration)
    # Resize/crop to fill the 1080x1920 frame first.
    base = _fit_cover(base)

    def scale(t):
        # Linear zoom from 1.0 -> zoom_end over the clip duration.
        frac = t / duration if duration else 0
        return 1.0 + (zoom_end - 1.0) * frac

    try:
        clip = base.resize(scale)
        clip = clip.set_position(("center", "center"))
        return clip
    except Exception as exc:
        log.warning("Ken-Burns resize failed (%s); using static image.", exc)
        return base


def _video_background(clip_paths, duration):
    """Concatenate / loop Pexels video clips with FAST CUTS to fill `duration`.

    Segments are joined with short crossfades for smooth, polished motion.
    """
    from moviepy.editor import VideoFileClip

    cut = get_cfg("video.clip_cut_seconds", 3.0)
    xfade = float(get_cfg("transitions.crossfade_seconds", 0.35))
    segments = []
    total = 0.0
    idx = 0
    guard = 0
    while clip_paths and guard < 200:
        # Account for crossfade overlap shrinking the composed length.
        effective = total - max(0, len(segments) - 1) * xfade
        if effective >= duration:
            break
        guard += 1
        path = clip_paths[idx % len(clip_paths)]
        idx += 1
        try:
            vc = VideoFileClip(path, audio=False)
        except Exception as exc:
            log.warning("Could not open clip %s (%s); skipping.", path, exc)
            continue
        seg_dur = min(cut, vc.duration or cut)
        if seg_dur <= 0:
            vc.close()
            continue
        seg = vc.subclip(0, seg_dur)
        seg = _fit_cover(seg)
        segments.append(seg)
        total += seg_dur
    if not segments:
        raise RuntimeError("No usable video segments.")
    bg = _concat_with_crossfade(segments, duration)
    bg = bg.set_duration(duration)
    return bg


def _images_background(image_paths, duration):
    """Build a Ken-Burns slideshow background from images covering `duration`.

    Segments are joined with short crossfades for smooth, polished motion.
    """
    if not image_paths:
        raise RuntimeError("No images for background.")
    xfade = float(get_cfg("transitions.crossfade_seconds", 0.35))
    per = max(2.5, duration / max(1, len(image_paths)))
    clips = []
    total = 0.0
    idx = 0
    guard = 0
    while guard < 200:
        effective = total - max(0, len(clips) - 1) * xfade
        if effective >= duration:
            break
        guard += 1
        path = image_paths[idx % len(image_paths)]
        idx += 1
        seg_dur = min(per, duration - effective)
        if seg_dur <= 0:
            break
        try:
            clips.append(_ken_burns_from_image(path, seg_dur))
            total += seg_dur
        except Exception as exc:
            log.warning("Ken-Burns failed for %s (%s).", path, exc)
            continue
    if not clips:
        raise RuntimeError("No Ken-Burns clips built.")
    bg = _concat_with_crossfade(clips, duration).set_duration(duration)
    return bg


def _warm_gradient_background(duration):
    """Animated WARM gradient (golden/peach/cream). Vectorized numpy.

    Falls back to a solid warm ColorClip on any error.
    """
    import numpy as np
    from moviepy.editor import VideoClip, ColorClip

    top = np.array(get_cfg("palette.gradient_top", [255, 224, 178]), dtype=np.float64)
    bottom = np.array(get_cfg("palette.gradient_bottom", [255, 183, 153]), dtype=np.float64)
    accent = np.array(get_cfg("palette.gradient_accent", [255, 245, 224]), dtype=np.float64)

    try:
        # Vertical gradient ramp (H,1,3) broadcast across width.
        ramp = np.linspace(0.0, 1.0, H, dtype=np.float64).reshape(H, 1, 1)
        base = top.reshape(1, 1, 3) * (1.0 - ramp) + bottom.reshape(1, 1, 3) * ramp

        def make_frame(t):
            # Gentle breathing shift toward the accent colour.
            phase = 0.5 + 0.5 * np.sin(2.0 * np.pi * t / 8.0)
            frame = base * (1.0 - 0.18 * phase) + accent.reshape(1, 1, 3) * (0.18 * phase)
            frame = np.clip(frame, 0, 255).astype("uint8")
            # Broadcast across the full width.
            return np.broadcast_to(frame, (H, W, 3)).copy()

        clip = VideoClip(make_frame, duration=duration)
        clip = clip.set_fps(FPS)
        log.info("Background source: warm animated gradient (last resort).")
        return clip
    except Exception as exc:
        log.warning("Gradient generation failed (%s); using solid warm color.", exc)
        solid = get_cfg("palette.solid_fallback", [255, 209, 168])
        return ColorClip(size=(W, H), color=tuple(solid)).set_duration(duration)


def _build_background(keywords, duration):
    """Background priority chain. Each source attempt is logged loudly.

    Chain: (1) Pexels VIDEO -> (2) Pexels PHOTOS (Ken-Burns) -> (3) warm
    gradient. Random/irrelevant keyless stock images (Picsum) are deliberately
    NOT used here: unrelated photos ruin a cute-pet reel, so a clean warm
    gradient is the preferred last resort.
    """
    # (1) Pexels VIDEO clips.
    try:
        clips = pexels_video.fetch_pexels_videos(keywords)
        if clips:
            log.info("Background source: Pexels VIDEO clips (%d).", len(clips))
            try:
                return _video_background(clips, duration)
            except Exception as exc:
                log.warning("Video background build failed (%s); trying photos.", exc)
    except Exception as exc:
        log.warning("Pexels video fetch error (%s); trying photos.", exc)

    # (2) Pexels PHOTOS as Ken-Burns.
    try:
        photos = images_mod.fetch_pexels_photos(keywords)
        if photos:
            log.info("Background source: Pexels PHOTOS (Ken-Burns, %d).", len(photos))
            try:
                return _images_background(photos, duration)
            except Exception as exc:
                log.warning("Photo background build failed (%s); using gradient.", exc)
    except Exception as exc:
        log.warning("Pexels photo fetch error (%s); using gradient.", exc)

    # (3) Warm animated gradient (clean last resort, always works).
    return _warm_gradient_background(duration)


# ==========================================================================
# Color grade — BRIGHT, VIVID, PUNCHY (no faded haze)
# ==========================================================================
def _apply_color_grade(clip):
    """Apply a SUBTLE bright/punchy grade directly to the background so cute
    colors pop: a gentle saturation/brightness multiply (colorx) plus a slight
    brightness + contrast lift (lum_contrast). This replaces the old faded
    warm-wash + heavy-vignette look. Fully defensive: returns the clip
    unchanged on any error so the reel always renders.
    """
    try:
        from moviepy.video.fx.all import colorx, lum_contrast
    except Exception as exc:
        log.warning("Color grade fx unavailable (%s); using ungraded background.", exc)
        return clip

    saturation = float(get_cfg("grade.saturation", 1.12))
    brightness = float(get_cfg("grade.brightness", 8))
    contrast = float(get_cfg("grade.contrast", 0.10))

    graded = clip
    try:
        # Mild multiply lifts brightness and makes colours pop (not oversaturated).
        graded = colorx(graded, saturation)
    except Exception as exc:
        log.warning("colorx grade failed (%s); skipping that step.", exc)
    try:
        # Slight brightness + contrast lift for crisp, clean footage.
        graded = lum_contrast(graded, lum=brightness, contrast=contrast)
    except Exception as exc:
        log.warning("lum_contrast grade failed (%s); skipping that step.", exc)

    log.info(
        "Applied bright/punchy grade (saturation=%.2f, brightness=%.0f, contrast=%.2f).",
        saturation, brightness, contrast,
    )
    return graded


def _build_cinematic_grade(duration):
    """Return SUBTLE overlay clips for a tasteful finish (NOT the old faded
    look). By default this is nearly off: an almost-invisible warm tint and a
    very soft vignette confined to the FAR corners only — never darkening the
    cute footage. Fully defensive: returns [] on any error.
    """
    overlays = []

    # (a) Very light warm tint (effectively off by default) ---------------
    try:
        from moviepy.editor import ColorClip

        warm = get_cfg("grade.warm_color", [255, 170, 110])
        warm_opacity = float(get_cfg("grade.warm_opacity", 0.04))
        if warm_opacity > 0:
            wash = (
                ColorClip(size=(W, H), color=tuple(int(c) for c in warm))
                .set_duration(duration)
                .set_opacity(warm_opacity)
            )
            overlays.append(wash)
    except Exception as exc:
        log.warning("Warm tint failed (%s); skipping.", exc)

    # (b) Soft vignette on FAR corners only -------------------------------
    try:
        import numpy as np
        from moviepy.editor import ImageClip

        strength = float(get_cfg("grade.vignette_strength", 0.15))
        if strength > 0:
            ys = np.linspace(-1.0, 1.0, H, dtype=np.float64).reshape(H, 1)
            xs = np.linspace(-1.0, 1.0, W, dtype=np.float64).reshape(1, W)
            radius = np.sqrt((xs ** 2) + (ys ** 2))
            # Only the far corners darken: ramp starts ~85% out.
            edge = np.clip((radius - 0.85) / 0.55, 0.0, 1.0)
            alpha = (edge * strength * 255.0).astype("uint8")  # (H, W)
            black = np.zeros((H, W, 3), dtype="uint8")
            mask = ImageClip(alpha, ismask=True).set_duration(duration)
            vignette = ImageClip(black).set_duration(duration).set_mask(mask)
            overlays.append(vignette)
    except Exception as exc:
        log.warning("Vignette generation failed (%s); skipping.", exc)

    if overlays:
        log.info("Applied subtle finish (%d overlay layer(s)).", len(overlays))
    return overlays


# ==========================================================================
# Captions
# ==========================================================================
def _make_text_clip(txt, fontsize, color, stroke_color, stroke_width, font, max_w):
    """Create a TextClip defensively. Returns None if rendering is unavailable."""
    from moviepy.editor import TextClip

    try:
        return TextClip(
            txt,
            fontsize=fontsize,
            color=color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            font=font,
            method="caption",
            size=(max_w, None),
            align="center",
        )
    except Exception as exc:
        log.warning("TextClip(caption) failed (%s); trying label mode.", exc)
        try:
            return TextClip(
                txt,
                fontsize=fontsize,
                color=color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                font=font,
            )
        except Exception as exc2:
            log.warning("TextClip(label) also failed (%s); skipping text.", exc2)
            return None


def _hex_to_rgb(value, default=(0, 0, 0)):
    """Parse a '#RRGGBB' hex color into an (r, g, b) tuple. Defensive."""
    try:
        s = str(value).strip().lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        if len(s) != 6:
            return default
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return default


def _make_caption_backdrop(tw, th, start, seg_dur, y_top):
    """Build a semi-transparent (optionally rounded) dark pill sized to the
    caption text so it reads cleanly on bright footage. Returns a positioned
    clip or None on any error.
    """
    try:
        import numpy as np
        from moviepy.editor import ColorClip, ImageClip

        opacity = float(get_cfg("captions.bg_opacity", 0.35))
        if opacity <= 0:
            return None
        color = _hex_to_rgb(get_cfg("captions.bg_color", "#000000"))
        rounded = bool(get_cfg("captions.rounded", True))

        pad_x = max(24, int(tw * 0.06))
        pad_y = max(16, int(th * 0.22))
        w = int(tw + 2 * pad_x)
        h = int(th + 2 * pad_y)
        if w <= 2 or h <= 2:
            return None

        alpha = np.ones((h, w), dtype=np.float64) * opacity
        if rounded:
            radius = int(min(h // 2, 48))
            if radius > 0:
                yy, xx = np.ogrid[0:h, 0:w]
                dx = np.minimum(xx, w - 1 - xx)
                dy = np.minimum(yy, h - 1 - yy)
                in_corner = (dx < radius) & (dy < radius)
                dist = np.sqrt((radius - dx) ** 2 + (radius - dy) ** 2)
                alpha[in_corner & (dist > radius)] = 0.0

        mask = ImageClip(alpha, ismask=True).set_duration(seg_dur)
        bg = (
            ColorClip(size=(w, h), color=color)
            .set_duration(seg_dur)
            .set_mask(mask)
            .set_start(start)
            .set_position(("center", int(y_top - pad_y)))
        )
        return bg
    except Exception as exc:
        log.warning("Caption backdrop failed (%s); showing text only.", exc)
        return None


def _build_caption_clips(text, duration):
    """Return a list of positioned caption clips (backdrops + text; may be empty)."""
    if not get_cfg("captions.enabled", True):
        return []

    groups = subtitles.build_caption_groups(text, duration)
    if not groups:
        return []

    fontsize = get_cfg("captions.fontsize", 90)
    color = get_cfg("captions.color", "white")
    stroke_color = get_cfg("captions.stroke_color", "black")
    stroke_width = get_cfg("captions.stroke_width", 4)
    font = get_cfg("captions.font", "DejaVu-Sans-Bold")
    y_ratio = get_cfg("captions.position_y_ratio", 0.72)
    max_w = int(W * 0.9)

    # Emotional power-words to highlight in a warm accent color.
    power_words = {"love", "sweet", "adorable", "family", "rescue", "heart",
                   "joy", "cute", "gentle", "precious"}
    accent = get_cfg("captions.accent_color", "#FFD27F")

    clips = []
    for g in groups:
        words = g["text"].split()
        is_power = any(w.strip(".,!?;:").lower() in power_words for w in words)
        use_color = accent if is_power else color
        tc = _make_text_clip(
            g["text"].upper(), fontsize, use_color, stroke_color, stroke_width, font, max_w
        )
        if tc is None:
            continue
        seg_dur = max(0.2, g["end"] - g["start"])
        y_top = int(H * y_ratio)
        try:
            tc = tc.set_start(g["start"]).set_duration(seg_dur)
            tc = tc.set_position(("center", y_top))
        except Exception as exc:
            log.warning("Could not place caption '%s' (%s).", g["text"], exc)
            continue

        # Add a backdrop pill BEHIND this caption (appended first so text is on top).
        try:
            tw, th = tc.size
            backdrop = _make_caption_backdrop(tw, th, g["start"], seg_dur, y_top)
            if backdrop is not None:
                clips.append(backdrop)
        except Exception as exc:
            log.warning("Caption backdrop sizing failed (%s); skipping backdrop.", exc)

        clips.append(tc)
    log.info("Built %d caption layer(s) (incl. backdrops).", len(clips))
    return clips


# ==========================================================================
# First-5-seconds HOOK overlay
# ==========================================================================
def _build_hook_clips(hook_text, background):
    """Return (overlay_clips, punched_background).

    Produces a big animated hook text with a scale "pop" entrance, a subtle
    flash, an optional semi-transparent backdrop band, and applies a brief
    background "punch" zoom for the hook window. Returns ([], background) if
    disabled or rendering fails.
    """
    if not get_cfg("hook.enabled", True) or not hook_text:
        return [], background

    hook_dur = float(get_cfg("hook.duration_seconds", 5.0))
    fontsize = get_cfg("hook.fontsize", 150)
    color = get_cfg("hook.color", "white")
    stroke_color = get_cfg("hook.stroke_color", "black")
    stroke_width = get_cfg("hook.stroke_width", 6)
    font = get_cfg("hook.font", "DejaVu-Sans-Bold")
    overshoot = float(get_cfg("hook.pop_overshoot", 1.18))
    pop_in = float(get_cfg("hook.pop_in_seconds", 0.45))
    punch_zoom = float(get_cfg("hook.punch_zoom", 1.12))
    flash_opacity = float(get_cfg("hook.flash_opacity", 0.35))
    backdrop_opacity = float(get_cfg("hook.backdrop_opacity", 0.35))

    overlays = []
    punched_bg = background

    # --- Background "punch" zoom for the hook window ---
    try:
        def punch_scale(t):
            if t >= hook_dur:
                return 1.0
            frac = t / hook_dur
            # Start zoomed in, settle back to 1.0 by the end of the hook.
            return 1.0 + (punch_zoom - 1.0) * (1.0 - frac)

        punched_bg = background.resize(punch_scale).set_position(("center", "center"))
    except Exception as exc:
        log.warning("Hook background punch failed (%s); keeping plain background.", exc)
        punched_bg = background

    # --- Subtle white flash at the very start ---
    try:
        from moviepy.editor import ColorClip

        flash = (
            ColorClip(size=(W, H), color=(255, 255, 255))
            .set_duration(min(0.35, hook_dur))
            .set_opacity(flash_opacity)
            .set_start(0)
        )
        overlays.append(flash)
    except Exception as exc:
        log.warning("Hook flash failed (%s); skipping flash.", exc)

    # --- Semi-transparent dark backdrop band so text pops off footage ---
    if backdrop_opacity > 0:
        try:
            from moviepy.editor import ColorClip

            band_h = int(H * 0.28)
            backdrop = (
                ColorClip(size=(W, band_h), color=(0, 0, 0))
                .set_duration(hook_dur)
                .set_opacity(backdrop_opacity)
                .set_start(0)
                .set_position(("center", "center"))
            )
            overlays.append(backdrop)
        except Exception as exc:
            log.warning("Hook backdrop band failed (%s); skipping.", exc)

    # --- Big animated hook text with pop entrance ---
    hook_clip = _make_text_clip(
        hook_text.upper(),
        fontsize,
        color,
        stroke_color,
        stroke_width,
        font,
        int(W * 0.92),
    )
    if hook_clip is not None:
        try:
            def pop(t):
                if t >= pop_in:
                    return 1.0
                frac = t / pop_in if pop_in else 1.0
                # Ease toward an overshoot then settle (simple ease-out + overshoot).
                return overshoot - (overshoot - 1.0) * (1.0 - frac)

            hook_clip = (
                hook_clip.set_start(0)
                .set_duration(hook_dur)
                .resize(pop)
                .set_position(("center", "center"))
            )
            overlays.append(hook_clip)
        except Exception as exc:
            log.warning("Hook text animation failed (%s); skipping hook text.", exc)
    else:
        log.warning("Hook text could not be rendered; continuing without it.")

    return overlays, punched_bg


# ==========================================================================
# Audio
# ==========================================================================
def _find_music_track():
    """Return a path to a music file in assets/music, or None."""
    try:
        for name in sorted(os.listdir(MUSIC_DIR)):
            if name == ".gitkeep":
                continue
            if name.lower().endswith((".mp3", ".m4a", ".wav", ".ogg", ".aac")):
                return os.path.join(MUSIC_DIR, name)
    except Exception:
        pass
    return None


def _build_audio(voice_path, duration):
    """Build the final audio track.

    Audio = voiceover (+ optional low-volume background music if a track exists
    in assets/music). Returns an AudioClip or None if the voiceover is missing.
    """
    from moviepy.editor import AudioFileClip, CompositeAudioClip
    from moviepy.audio.fx.all import audio_loop, volumex

    if not voice_path or not os.path.exists(voice_path):
        log.error("Voiceover file missing (%s); cannot build audio.", voice_path)
        return None

    try:
        voice = AudioFileClip(voice_path)
    except Exception as exc:
        log.error("Could not open voiceover (%s).", exc)
        return None

    tracks = [voice]

    if get_cfg("music.enabled", True):
        music_path = _find_music_track()
        if music_path:
            try:
                vol = float(get_cfg("music.volume", 0.13))
                music = AudioFileClip(music_path)
                music = volumex(music, vol)
                # Loop/trim music to match the voiceover duration.
                try:
                    music = audio_loop(music, duration=voice.duration)
                except Exception:
                    music = music.set_duration(min(music.duration, voice.duration))
                tracks.append(music)
                log.info("Mixed background music at %.0f%% volume: %s", vol * 100, os.path.basename(music_path))
            except Exception as exc:
                log.warning("Could not mix music (%s); voiceover only.", exc)

    if len(tracks) == 1:
        return voice
    try:
        return CompositeAudioClip(tracks).set_duration(voice.duration)
    except Exception as exc:
        log.warning("Audio mix failed (%s); using voiceover only.", exc)
        return voice


# ==========================================================================
# Public API
# ==========================================================================
def compose_video(voice_path, text, keywords, hook_text=None, out_path=None):
    """Compose the full reel and write it to disk. Returns the output path.

    Parameters
    ----------
    voice_path : str   Path to the narration mp3 (required).
    text       : str   The narration text (for captions).
    keywords   : list  Footage search keywords for the background.
    hook_text  : str   The derived first-5s hook line (optional).
    out_path   : str   Output mp4 path (optional; auto-named if omitted).
    """
    from moviepy.editor import AudioFileClip, CompositeVideoClip

    if not voice_path or not os.path.exists(voice_path):
        raise FileNotFoundError("Voiceover not found: %s" % voice_path)

    # Determine duration from the voiceover.
    probe = AudioFileClip(voice_path)
    duration = float(probe.duration or get_cfg("video.target_duration_seconds", 60))
    probe.close()
    duration = max(get_cfg("video.min_duration_seconds", 10), duration)
    log.info("Target reel duration: %.2fs", duration)

    # 1) Background.
    background = _build_background(keywords, duration)
    background = background.set_duration(duration)

    # 1b) Bright/punchy color grade directly on the background (kills the
    # faded look). Defensive: returns the background unchanged on failure.
    if get_cfg("grade.enabled", True):
        background = _apply_color_grade(background)
        background = background.set_duration(duration)

    # 2) Hook overlay (+ background punch) for the first ~5s.
    suppress_captions_during_hook = get_cfg("hook.suppress_captions", True)
    hook_dur = float(get_cfg("hook.duration_seconds", 5.0))
    hook_overlays, background = _build_hook_clips(hook_text, background)
    background = background.set_duration(duration)

    layers = [background]

    # 2b) Subtle finish (very light tint + far-corner vignette) on top of the
    # graded background, below captions/hook so text stays crisp and readable.
    if get_cfg("grade.enabled", True):
        layers.extend(_build_cinematic_grade(duration))

    # 3) Captions (optionally suppressed during the hook window).
    caption_clips = _build_caption_clips(text, duration)
    if hook_overlays and suppress_captions_during_hook:
        kept = []
        for c in caption_clips:
            try:
                if c.start is not None and c.start >= hook_dur:
                    kept.append(c)
            except Exception:
                kept.append(c)
        caption_clips = kept
    layers.extend(caption_clips)

    # 4) Hook overlays go on top.
    layers.extend(hook_overlays)

    video = CompositeVideoClip(layers, size=(W, H)).set_duration(duration)

    # 5) Audio.
    audio = _build_audio(voice_path, duration)
    if audio is not None:
        video = video.set_audio(audio)

    # 6) Write out.
    if out_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        stamp = random.randint(1000, 9999)
        out_path = os.path.join(OUTPUT_DIR, "sweetsoul_%d.mp4" % stamp)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    log.info("Rendering reel -> %s", out_path)
    # High-quality encoding: ~6 Mbps bitrate, yuv420p for broad compatibility.
    write_kwargs = dict(
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        threads=4,
        preset=get_cfg("video.preset", "medium"),
        verbose=False,
        logger=None,
    )
    try:
        # Prefer CONSTANT-QUALITY (CRF) encoding: it allocates as many bits as
        # the footage needs so high-motion cute clips stay crisp instead of
        # going blocky/pixelated at a fixed low bitrate. CRF ~18-21 is visually
        # lossless-ish; lower = higher quality + bigger file.
        ffmpeg_params = ["-pix_fmt", "yuv420p"]
        crf = get_cfg("video.crf", 20)
        if crf is not None:
            ffmpeg_params += ["-crf", str(int(crf))]
            # With CRF active, do NOT also pass a target bitrate (it would
            # override constant-quality). Keep an optional high ceiling only.
            bitrate = get_cfg("video.bitrate", None)
            if bitrate:
                ffmpeg_params += ["-maxrate", str(bitrate), "-bufsize", "24000k"]
        else:
            bitrate = get_cfg("video.bitrate", "12000k")
            if bitrate:
                write_kwargs["bitrate"] = bitrate
        write_kwargs["ffmpeg_params"] = ffmpeg_params
    except Exception as exc:
        log.warning("Could not set HQ encoding params (%s); using defaults.", exc)

    try:
        video.write_videofile(out_path, **write_kwargs)
    except Exception as exc:
        log.warning("HQ write failed (%s); retrying with safe defaults.", exc)
        video.write_videofile(
            out_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
            ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "20"],
            verbose=False,
            logger=None,
        )
    try:
        video.close()
    except Exception:
        pass
    log.info("Reel written: %s", out_path)
    return out_path
