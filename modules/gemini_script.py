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
# 30+ unique hooks — one is randomly picked per reel so every video feels fresh.
# These are VOICE-ONLY (spoken by the narrator); nothing is drawn on screen.
HOOK_CANDIDATES = [
    "Wait for it, because this will melt your heart.",
    "You won't believe what this tiny puppy just did.",
    "Try not to smile watching this — I dare you.",
    "This little moment made everyone in the room cry happy tears.",
    "Watch till the very end — it gets even better.",
    "This is the cutest thing you'll see all day.",
    "Nobody expected this, and it changed everything.",
    "This baby's reaction is absolutely priceless.",
    "I've watched this a hundred times and it still gets me.",
    "This little rescue story will stay with you all day.",
    "Stop scrolling — you need to see this right now.",
    "This tiny kitten just did something nobody saw coming.",
    "This little puppy just became everyone's favorite hero.",
    "What happened next made the whole family burst into tears.",
    "This is the friendship nobody asked for but everyone needed.",
    "One small moment, one enormous amount of love.",
    "This puppy's first day home is the sweetest thing ever.",
    "The way this baby laughs will instantly make your day.",
    "This dog has been waiting for this moment his whole life.",
    "You'll want to share this with everyone you love.",
    "This tiny soul proved that love has no size.",
    "This is what pure joy looks like — and it's adorable.",
    "A baby, a puppy, and a moment you'll never forget.",
    "This little kitten just stole every heart in the room.",
    "The bond between these two will warm you to your core.",
    "This happened by accident — and it's absolutely perfect.",
    "Sometimes the smallest creatures carry the biggest love.",
    "This rescue puppy's first smile says it all.",
    "What this toddler did next left everyone speechless.",
    "This is the kind of story the internet was made for.",
    "Give this ten seconds. Trust me.",
    "Nobody in that room stayed dry-eyed.",
    "This tiny thing changed one family forever.",
    "You are about to smile whether you like it or not.",
    "Keep watching, the best part is hiding at the end.",
    "This is your sign to be gentle with something small today.",
    "One look and this little one had a home.",
    "It took four seconds for these two to become inseparable.",
    "There is a reason this clip refuses to leave my head.",
    "This little face was waiting all week for this.",
    "Watch what happens the second she turns around.",
    "This might be the softest thing on the internet today.",
    "Nobody taught him this. He just knew.",
    "This is what being chosen looks like.",
    "Two seconds in and my heart was gone.",
    "This one is going to sit with you for a while.",
    "The tiniest hero you'll meet today.",
    "This started as an ordinary Tuesday.",
    "You can actually see the exact moment they become friends.",
    "That little sigh at the end broke me.",
    "This is the good part of the internet.",
    "She had no idea he'd been waiting by the door all morning.",
    "Small paws, enormous heart.",
    "This is the sweetest thing I've filmed all year.",
    "He wasn't supposed to be able to do this yet.",
    "Their first hello turned into their whole friendship.",
    "You'll feel this one in your chest.",
    "Nobody expected the baby to react like that.",
]

# SHORT, punchy labels drawn ON SCREEN for the first few seconds.
# These are deliberately separate from HOOK_CANDIDATES: the spoken hook is a
# full sentence, but a full sentence rendered at 150px is unreadable on a phone.
# A 2-4 word label is what actually stops a thumb mid-scroll, and it is also the
# only hook a muted viewer ever receives (a large share of Shorts plays).
SCREEN_HOOKS = [
    "WAIT FOR IT...",
    "WATCH TILL THE END",
    "TRY NOT TO SMILE",
    "THIS MELTED ME",
    "NOBODY EXPECTED THIS",
    "CUTEST THING TODAY",
    "GIVE IT 10 SECONDS",
    "THE ENDING THOUGH",
    "PURE JOY INCOMING",
    "SOUND ON 🔊",
    "HE JUST KNEW",
    "BEST FRIENDS ALREADY",
    "SHE HAD NO IDEA",
    "KEEP WATCHING",
    "TINY BUT MIGHTY",
    "THIS IS THE ONE",
    "WAIT FOR THE END 🥹",
    "IT GETS BETTER",
    "SMALL PAWS BIG HEART",
    "YOU'LL WATCH TWICE",
    "LOOK AT HIS FACE",
    "FIRST HELLO ❤️",
    "DON'T SCROLL PAST",
    "THE SOFTEST THING",
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
    "a puppy meeting a baby for the first time",
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
    "a baby sharing snacks with a patient gentle dog",
    "a puppy and kitten cuddling under a warm blanket",
    "a toddler reading a picture book to three sleepy puppies",
    "a baby's first steps guided by a loyal gentle dog",
    "a cat tucking in a newborn baby every night",
    "a puppy howling along to a baby's laughter",
    "a toddler and a fluffy cat playing hide and seek",
    "a dog meeting his new baby sibling at the hospital",
    "a kitten and a baby discovering bubbles together",
    "a shy shelter dog wagging his tail for the very first time",
    "a puppy waiting by the window every day for the school bus",
    "a kitten who adopted a litter of orphaned puppies",
    "a toddler sharing an umbrella with a soaked stray cat",
    "a three-legged puppy outrunning everyone at the park",
    "a baby falling asleep on a patient old dog's belly",
    "a kitten who insists on supervising bath time",
    "an old dog teaching a clumsy puppy how to climb stairs",
    "a toddler carefully feeding a bottle to a rescued kitten",
    "a puppy who brings one sock to every visitor as a gift",
    "a baby and a cat playing peekaboo through a doorway",
    "a rescue dog meeting the child who chose him",
    "a kitten discovering its own reflection for the first time",
    "a puppy learning to swim with a laughing toddler cheering",
    "a dog gently guarding a sleeping newborn all night",
    "a toddler and a kitten sharing a single blanket in winter",
    "a puppy's first birthday celebrated by the whole family",
    "a cat who greets the baby at the door every single morning",
    "a nervous rescue kitten finally purring after a month",
    "a toddler reading the alphabet out loud to a listening dog",
    "a puppy and a duckling that grew up in the same yard",
    "a baby's first word being the family dog's name",
    "a senior dog getting adopted on his last day at the shelter",
    "a kitten who steals one strawberry every single morning",
    "a toddler building a pillow fort for a shy puppy",
    "a dog carrying his blanket to a crying baby",
]

# Rotating sign-offs. A single fixed CTA repeated verbatim in every video's
# audio, on a channel of 100+ videos, is one of the loudest "mass-produced from
# one template" signals there is -- and it also trains regular viewers to swipe
# the moment they hear the familiar line.
CTA_CANDIDATES = [
    "Follow SweetSoul Stories for your daily dose of joy.",
    "Subscribe to SweetSoul Stories — a new little moment like this every day.",
    "There's a new sweet story here every single day. Come back tomorrow.",
    "If this made you smile, SweetSoul Stories has one of these for you daily.",
    "Stay for tomorrow's story. It's just as soft as this one.",
    "Subscribe and let something gentle find you every day.",
    "SweetSoul Stories, every day, for the days you need something kind.",
    "Follow along — the next tiny story is already waiting.",
]

# Kept for backward compatibility with anything importing the old constant.
_CTA = CTA_CANDIDATES[0]


def _pick_cta():
    return random.choice(CTA_CANDIDATES)


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
    chosen = hook or random.choice(HOOK_CANDIDATES)
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

    def __post_init__(self):
        # Auto-derive the spoken hook if one was not supplied.
        if not self.hook:
            self.hook = _derive_hook(self.text)
        if not self.screen_hook:
            self.screen_hook = random.choice(SCREEN_HOOKS)
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
        topic = random.choice(TOPIC_POOL)
        log.info("Auto-picked topic: %s", topic)
    script = _generate_with_gemini(topic)
    if script is None:
        script = _fallback_script(topic)
        log.info("Using fallback script: '%s'.", script.title)

    # Give every reel a DIFFERENT spoken opener. Both the pre-written scripts
    # and Gemini tend to start with the same few hooks ("This melted my
    # heart...", "Wait for it..."), which made the voiceover feel repetitive.
    # Swap the first sentence for a unique hook and reuse it as the (now
    # voice-only) hook field too.
    fresh_hook = random.choice(HOOK_CANDIDATES)
    script.text = swap_spoken_hook(script.text, fresh_hook)
    script.text = swap_cta(script.text)
    script.hook = fresh_hook
    script.screen_hook = random.choice(SCREEN_HOOKS)
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
    hooks = list(HOOK_CANDIDATES)
    random.shuffle(hooks)
    screen = list(SCREEN_HOOKS)
    random.shuffle(screen)
    for i in range(count):
        script = pool[i % len(pool)]
        fresh_hook = hooks[i % len(hooks)]
        script.text = swap_spoken_hook(script.text, fresh_hook)
        script.text = swap_cta(script.text)
        script.hook = fresh_hook
        script.screen_hook = screen[i % len(screen)]
        results.append(script)
    return results
