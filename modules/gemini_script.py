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
from dataclasses import dataclass, field

from .config import QUOTES_PATH, get_cfg, get_env

log = logging.getLogger("sweetsoul.gemini")

# Short, emotional, curiosity-driven hook openers for the cute/pets niche.
HOOK_CANDIDATES = [
    "WAIT FOR IT...",
    "THIS MELTED MY HEART",
    "YOU WON'T BELIEVE THIS",
    "WATCH TILL THE END",
    "THE CUTEST THING TODAY",
    "TRY NOT TO SMILE",
]

DEFAULT_KEYWORDS = [
    "golden retriever puppy outdoor sunshine",
    "puppy playing in grass sunlight",
    "baby laughing outdoor",
    "kitten playing near window light",
    "toddler playing with puppy outside",
    "dog and baby in garden",
    "fluffy puppy running outdoor",
    "baby and puppy sunny day",
    "kittens playing in sunlight",
    "child hugging dog outdoor",
]

# Diverse topic pool — randomly picked each run for variety
TOPIC_POOL = [
    "a golden retriever puppy meeting a baby for the first time",
    "a kitten and puppy becoming best friends",
    "a toddler teaching a puppy to sit",
    "a baby's first giggle triggered by a playful dog",
    "a rescue kitten finding a forever home",
    "twin babies playing with a gentle giant dog",
    "a puppy discovering snow for the first time",
    "a kitten stealing a baby's toy and returning it",
    "a toddler and puppy taking a nap together",
    "a dog proudly carrying his puppy to meet the family baby",
    "a kitten learning to play fetch with a laughing toddler",
    "a baby sharing snacks with a patient golden retriever",
    "a puppy and kitten cuddling under a warm blanket",
    "a toddler reading a picture book to three sleepy puppies",
    "a baby's first steps guided by a loyal labrador",
    "a cat tucking in a newborn baby every night",
    "a puppy howling along to a baby's laughter",
    "a toddler and a fluffy cat playing hide and seek",
    "a dog meeting his new baby sibling at the hospital",
    "a kitten and a baby discovering bubbles together",
]

_CTA = "Follow SweetSoul Stories for your daily dose of joy."


def _derive_hook(text):
    """Derive a short, punchy UPPERCASE hook line from a script.

    If the first sentence already reads like a hook (short and punchy) we use
    it; otherwise we pick a curiosity-driven candidate. Always UPPERCASE.
    """
    if not text:
        return random.choice(HOOK_CANDIDATES)

    # Grab the first sentence / clause.
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    # Further trim on a comma if the lead-in clause is itself a hook.
    lead = first.split(",")[0].strip()

    words = lead.split()
    # A good on-screen hook is short. If the lead clause is short enough, use it.
    if 2 <= len(words) <= 6:
        return lead.upper().rstrip(".")

    # Otherwise fall back to a curated candidate.
    return random.choice(HOOK_CANDIDATES)


@dataclass
class Script:
    """A single narration script ready for the pipeline."""

    title: str
    text: str
    keywords: list = field(default_factory=list)
    hook: str = ""

    def __post_init__(self):
        # Auto-derive the on-screen hook if one was not supplied.
        if not self.hook:
            self.hook = _derive_hook(self.text)
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
  makes people stop scrolling. Good examples: "Wait for it...", "You won't
  believe this", "This melted my heart", "Watch till the end", "Try not to
  smile".
- Warm, sweet, gentle, wholesome, feel-good emotional tone. Like a kind older
  sister narrating a cute story.
- Tell a tiny heartwarming story about adorable animals PLAYING and having fun
  together (puppies, kittens, dogs, cats) and/or playing with cute human
  children (babies and toddlers) - playful, joyful "aww" moments.
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
        words=target_words, cta=_CTA, topic_line=topic_line
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
            # Guarantee the CTA is present.
            if _CTA.lower() not in script.text.lower():
                script.text = script.text.rstrip() + " " + _CTA
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
        topic = random.choice(TOPIC_POOL)
        log.info("Auto-picked topic: %s", topic)
    script = _generate_with_gemini(topic)
    if script is None:
        script = _fallback_script(topic)
        log.info("Using fallback script: '%s'.", script.title)
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
    for i in range(count):
        results.append(pool[i % len(pool)])
    return results
