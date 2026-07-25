"""
Script generation for SweetSoul Stories.

Generates ~150-word / ~60s heartwarming narration about adorable pets and/or
babies using Google's Gemini API. If no API key is configured, or every model
candidate fails, it falls back to the bundled quotes.json of pre-written
wholesome scripts.

Heavy third-party libraries (google-generativeai) are imported lazily inside
functions so that importing this module never hard-fails in environments where
the dependency is not installed.
"""

import json
import logging
import random
import re
from dataclasses import dataclass, field, replace

from .config import QUOTES_PATH, get_cfg, get_env

log = logging.getLogger("sweetsoul.gemini")

# All content pools now live in modules/pools.py so they can be grown in one
# place. Re-exported under their original names so any other import keeps working.
#
#   topics 46 -> 150 | spoken hooks 58 -> 120 | screen hooks 24 -> 80
#   flash phrases (new) 152 | sign-offs 8 -> 45
#
# Selection goes through modules/history.py, which draws WITHOUT replacement and
# remembers across runs, so nothing repeats until a pool is genuinely exhausted.
from .pools import (
    CTA_CANDIDATES,
    DEFAULT_KEYWORDS,
    FLASH_PHRASES,
    HOOK_CANDIDATES,
    SCREEN_HOOKS,
    TOPIC_POOL,
)
from . import history

_CTA = CTA_CANDIDATES[0]


def _pick_cta():
    return history.pick("ctas", CTA_CANDIDATES)


def _pick_screen_hook():
    return history.pick("screen_hooks", SCREEN_HOOKS)


def _pick_flashes(count=3):
    """Short phrases flashed mid-video (see video_composer._build_flash_clips).

    Drawn through history so the same three words are not stamped across a
    week of uploads, which is exactly the kind of repetition that made the old
    on-screen text feel templated.
    """
    picked = history.pick("flashes", FLASH_PHRASES, count=count)
    return picked if isinstance(picked, list) else [picked]


def _has_cta(text):
    """True if the script already ends with one of our sign-offs."""
    low = (text or "").lower()
    return any(c.lower() in low for c in CTA_CANDIDATES)


def _derive_hook(text):
    """Pick a unique, voice-friendly hook sentence for this reel.

    Instead of trying to extract a hook from the script text (which often
    produces stiff or duplicate phrases), we always pick randomly from the
    curated HOOK_CANDIDATES list. This guarantees:
      - Every reel gets a different spoken hook opener.
      - The hook is a natural spoken sentence, not an uppercase screen label.
      - No two reels in a batch share the same hook.
    """
    # Plain random on purpose, NOT history.pick(). This runs inside
    # Script.__post_init__, and load_fallback_scripts() builds a Script for every
    # entry in quotes.json - 23 of them - on a single reel. Consuming history
    # here drained the hook, screen-hook and flash pools in one run and forced
    # an immediate reset, which is what caused visible repeats. The real,
    # history-backed pick happens once per reel in generate_script().
    return random.choice(HOOK_CANDIDATES)


def swap_spoken_hook(text, hook=None):
    """Replace the FIRST sentence of the script with a fresh spoken hook.

    The narrator voices `script.text`, and almost every pre-written / Gemini
    script begins with the same handful of openers ("This melted my heart...",
    "Wait for it...", "You won't believe..."). That makes the SPOKEN hook feel
    repetitive across reels even though the on-screen text is gone.

    This swaps out that first sentence for a randomly chosen unique hook from
    HOOK_CANDIDATES so every reel's voiceover opens differently, while leaving
    the rest of the story (and the closing CTA) completely untouched.
    """
    if not text:
        return text
    chosen = hook or history.pick("hooks", HOOK_CANDIDATES)
    body = text.strip()
    # Split off the first sentence (ends at the first ., ! or ?).
    parts = re.split(r"(?<=[.!?])\s+", body, maxsplit=1)
    rest = parts[1].strip() if len(parts) == 2 else ""
    if rest:
        return f"{chosen} {rest}"
    # No clear sentence break — just prepend the hook.
    return f"{chosen} {body}"


def swap_cta(text, cta=None):
    """Replace a known trailing sign-off with a freshly chosen one.

    quotes.json and older Gemini output both end on the same fixed line
    ("Follow SweetSoul Stories for your daily dose of joy."). Rotating it means
    the last five seconds of audio -- the part regulars hear most often -- is no
    longer identical across the whole library.
    """
    if not text:
        return text
    body = text.strip()
    chosen = cta or _pick_cta()
    for candidate in CTA_CANDIDATES:
        idx = body.lower().rfind(candidate.lower())
        if idx != -1:
            return (body[:idx].rstrip() + " " + chosen).strip()
    if not _has_cta(body):
        return (body + " " + chosen).strip()
    return body


@dataclass
class Script:
    """A single narration script ready for the pipeline."""

    title: str
    text: str
    keywords: list = field(default_factory=list)
    hook: str = ""          # spoken opener (full sentence, narrated)
    screen_hook: str = ""   # on-screen label (2-4 words, drawn for ~2.5s)
    flashes: list = field(default_factory=list)  # short phrases flashed mid-video

    def __post_init__(self):
        # Auto-derive the spoken hook if one was not supplied.
        if not self.hook:
            self.hook = _derive_hook(self.text)
        # Cheap random placeholders only. generate_script() overwrites both with
        # history-backed picks for the reel that is actually produced; see the
        # note in _derive_hook for why this must not touch history.
        if not self.screen_hook:
            self.screen_hook = random.choice(SCREEN_HOOKS)
        if not self.flashes:
            self.flashes = random.sample(FLASH_PHRASES, min(3, len(FLASH_PHRASES)))
        # Ensure we always have at least some footage keywords.
        if not self.keywords:
            self.keywords = list(DEFAULT_KEYWORDS)

    @property
    def word_count(self):
        return len(self.text.split())


# --------------------------------------------------------------------------
# Gemini-backed generation
# --------------------------------------------------------------------------
_PROMPT_TEMPLATE = """You are a scriptwriter for a faceless YouTube Shorts channel called
"SweetSoul Stories". The niche is HEARTWARMING, CUTE PETS & BABIES: adorable
dogs and cats, cute babies and toddlers, and the sweet "aww" moments between
them. The audience is in the USA.

Write ONE narration script of about {words} words (roughly 30 seconds when
read aloud at a gentle pace). Requirements:
- Sentence 1 MUST be a SHORT scroll-stopping curiosity hook (3-7 words) that
  makes people stop scrolling. Vary it every time and be creative — there are
  many ways to hook a viewer. Good styles: a teaser ("Wait for it..."),
  a promise ("This will make your day"), a challenge ("Try not to smile"),
  or curiosity ("You won't believe what happened next"). Do NOT reuse the same
  opener every time.
- Warm, sweet, gentle, wholesome, feel-good emotional tone. Like a kind older
  sister narrating a cute story.
- Tell a tiny heartwarming story about adorable animals PLAYING and having fun
  together (puppies, kittens, dogs, cats) and/or playing with cute human
  children (babies and toddlers) - playful, joyful "aww" moments.
- Do NOT state a specific dog or cat BREED (no "golden retriever", "labrador",
  "husky", etc.). The footage is random stock video, so we never know the real
  breed. Refer to the animal generically: "the puppy", "this little dog",
  "the fluffy pup", "the kitten", "the cat".
- Do NOT give the pet a name. Do NOT use common pet names like "Leo", "Max",
  "Bella", "Luna", "Charlie", "Milo". Refer to it only as "the puppy", "the
  little one", "this sweet pup", etc. Never call the animal by a proper name.
- Keep it SHORT and punchy — 30 seconds max when spoken. Do NOT ramble.
- End with this exact call to action: "{cta}"
- Plain spoken sentences only. No emojis, no stage directions, no markdown,
  no hashtags, no quotation marks around the whole thing. American English.
{topic_line}
Return ONLY a JSON object (no code fences) with these keys:
  "title": a short catchy title (max 8 words),
  "text": the full narration script as a single string,
  "keywords": an array of 3-5 short footage search phrases describing the
              PLAYFUL pets/children in the story. Each phrase MUST describe an
              action/interaction, e.g. "puppies playing together",
              "dog playing with baby", "toddler playing with kitten".
"""


def _build_prompt(topic=None):
    target_words = get_cfg("gemini.target_words", 150)
    topic_line = ""
    if topic:
        topic_line = f"- The story should be about: {topic}\n"
    return _PROMPT_TEMPLATE.format(
        words=target_words, cta=_pick_cta(), topic_line=topic_line
    )


def _parse_model_json(raw):
    """Extract a JSON object from a model response that may include fences."""
    if not raw:
        return None
    cleaned = raw.strip()
    # Strip code fences if present.
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # Find the outermost JSON object.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except Exception:
        return None


def _generate_with_gemini(topic=None):
    """Try Gemini across the ordered model candidates. Returns Script or None."""
    api_key = get_env("GEMINI_API_KEY")
    if not api_key:
        log.warning("GEMINI_API_KEY not set - using local quotes.json fallback.")
        return None

    try:
        import google.generativeai as genai
    except Exception as exc:
        log.warning("google-generativeai not available (%s); using fallback.", exc)
        return None

    try:
        genai.configure(api_key=api_key)
    except Exception as exc:
        log.warning("Could not configure Gemini (%s); using fallback.", exc)
        return None

    default_model = get_env("GEMINI_MODEL", get_cfg("gemini.model", "gemini-2.0-flash"))
    candidates = get_cfg(
        "gemini.model_candidates",
        ["gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash"],
    )
    # Make sure the configured default is tried first, without duplicates.
    ordered = [default_model] + [m for m in candidates if m != default_model]

    prompt = _build_prompt(topic)
    temperature = get_cfg("gemini.temperature", 0.9)

    for model_name in ordered:
        try:
            log.info("Requesting script from Gemini model '%s'...", model_name)
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(
                prompt,
                generation_config={"temperature": temperature},
            )
            raw = getattr(resp, "text", None)
            data = _parse_model_json(raw)
            if not data or not data.get("text"):
                log.warning("Model '%s' returned no usable text; trying next.", model_name)
                continue
            script = Script(
                title=str(data.get("title") or "A SweetSoul Story").strip(),
                text=str(data["text"]).strip(),
                keywords=[str(k).strip() for k in data.get("keywords", []) if str(k).strip()],
            )
            # Guarantee a sign-off is present (any of the rotating variants).
            if not _has_cta(script.text):
                script.text = script.text.rstrip() + " " + _pick_cta()
            log.info("Gemini script ready via '%s' (%d words).", model_name, script.word_count)
            return script
        except Exception as exc:
            log.warning("Gemini model '%s' failed (%s); trying next.", model_name, exc)
            continue

    log.warning("All Gemini model candidates failed - using local quotes.json.")
    return None


# --------------------------------------------------------------------------
# Local fallback
# --------------------------------------------------------------------------
def load_fallback_scripts():
    """Load all pre-written scripts from quotes.json as Script objects."""
    try:
        with open(QUOTES_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        items = data.get("scripts", []) if isinstance(data, dict) else data
        scripts = []
        for item in items:
            try:
                scripts.append(
                    Script(
                        title=str(item.get("title", "A SweetSoul Story")),
                        text=str(item["text"]),
                        keywords=list(item.get("keywords", [])),
                    )
                )
            except Exception:
                continue
        return scripts
    except Exception as exc:
        log.error("Could not load quotes.json (%s).", exc)
        return []


def _fallback_script(topic=None):
    scripts = load_fallback_scripts()
    if not scripts:
        # Absolute last-resort hard-coded script.
        return Script(
            title="A SweetSoul Story",
            text=(
                "Wait for it, because this little moment will melt your heart. "
                "A tiny puppy curled up beside a sleeping baby, keeping watch "
                "like a gentle little guardian. Moments like these remind us how "
                "much love the smallest souls can hold. " + _CTA
            ),
            keywords=list(DEFAULT_KEYWORDS),
        )
    return random.choice(scripts)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def generate_script(topic=None):
    """Return a single Script, preferring Gemini and falling back to quotes.

    If no topic is given, a random one is picked from TOPIC_POOL so every
    run produces a genuinely different story (no repeat syndrome).
    """
    if not topic:
        topic = history.pick("topics", TOPIC_POOL)
        log.info(
            "Auto-picked topic: %s  (%d of %d unused)",
            topic, len(history.remaining("topics", TOPIC_POOL)), len(TOPIC_POOL),
        )
    script = _generate_with_gemini(topic)
    if script is None:
        script = _fallback_script(topic)
        log.info("Using fallback script: '%s'.", script.title)

    # Give every reel a DIFFERENT spoken opener. Both the pre-written scripts
    # and Gemini tend to start with the same few hooks ("This melted my
    # heart...", "Wait for it..."), which made the voiceover feel repetitive.
    # Swap the first sentence for a unique hook and reuse it as the (now
    # voice-only) hook field too.
    fresh_hook = history.pick("hooks", HOOK_CANDIDATES)
    script.text = swap_spoken_hook(script.text, fresh_hook)
    script.text = swap_cta(script.text)
    script.hook = fresh_hook
    script.screen_hook = _pick_screen_hook()
    script.flashes = _pick_flashes()
    return script


def generate_scripts(count, topic=None):
    """Return `count` Scripts. Uses Gemini per item when available, else
    fills from unique fallback scripts to avoid repeats within a batch."""
    count = max(1, int(count))
    results = []

    api_key = get_env("GEMINI_API_KEY")
    if api_key:
        for _ in range(count):
            results.append(generate_script(topic))
        return results

    # No API key: draw unique fallback scripts where possible.
    pool = load_fallback_scripts()
    random.shuffle(pool)
    if not pool:
        return [generate_script(topic) for _ in range(count)]
    # Give each reel in the batch a DIFFERENT spoken hook (no repeats while we
    # still have unused hooks to hand out).
    for i in range(count):
        # COPY, don't reuse. quotes.json holds 23 scripts, so once `count`
        # exceeds that, `pool[i % len(pool)]` hands back an object that is
        # already in `results`. Mutating it then overwrote the hook and screen
        # hook of the earlier reel too, so a batch of 40 produced only 23
        # distinct openers. Real scheduled runs call generate_script() once per
        # reel and were unaffected, but batch runs and the SEO self-check were.
        script = replace(pool[i % len(pool)])
        fresh_hook = history.pick("hooks", HOOK_CANDIDATES)
        script.text = swap_spoken_hook(script.text, fresh_hook)
        script.text = swap_cta(script.text)
        script.hook = fresh_hook
        script.screen_hook = _pick_screen_hook()
        script.flashes = _pick_flashes()
        results.append(script)
    return results
