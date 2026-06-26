"""
Long-form moral-story generation for MoralTales.

Produces a ~5-7 minute (about 750-1000 word) narrated MORAL STORY for kids in
American English using Google's Gemini API. If no API key is configured, or
every model candidate fails, it falls back to the bundled stories.json of
pre-written stories.

The script is engineered for RETENTION:
  * A 1-2 sentence scroll-stopping HOOK as the opener.
  * "Open loops" / mini cliffhangers sprinkled through the story so viewers
    keep watching to find out what happens.
  * A clear, satisfying MORAL stated plainly near the end.
  * A spoken call-to-action close.

Heavy third-party libraries are imported lazily so importing this module never
hard-fails where the dependency is missing.
"""

import json
import logging
import random
import re
from dataclasses import dataclass, field

from .config import STORIES_PATH, get_cfg, get_env

log = logging.getLogger("moraltales.story")

# Diverse moral-lesson seeds. One is picked per run so every episode teaches a
# different lesson with a fresh setting and characters (no repeats).
TOPIC_POOL = [
    ("honesty", "a child who finds a lost wallet full of money"),
    ("kindness", "a lonely old man and the children who befriend him"),
    ("hard work", "a lazy rabbit who laughs at a slow but steady tortoise"),
    ("courage", "a small boy who must cross a dark forest to fetch medicine"),
    ("greed", "a fisherman who catches a magical fish that grants wishes"),
    ("patience", "a girl who plants a seed and waits through every season"),
    ("humility", "a proud peacock who learns the value of every creature"),
    ("forgiveness", "two best friends torn apart by a silly misunderstanding"),
    ("gratitude", "a poor boy who shares his only meal with a stranger"),
    ("helping others", "village children who rebuild an old woman's broken bridge"),
    ("never giving up", "a young bird afraid to take its very first flight"),
    ("teamwork", "ants who must move a giant crumb before the rain comes"),
    ("respecting elders", "a clever grandson and his wise old grandmother"),
    ("sharing", "two brothers and a single basket of mangoes"),
    ("telling the truth", "a shepherd boy who cried wolf one too many times"),
    ("self-belief", "a tiny elephant told he could never do anything big"),
    ("compassion", "a child who rescues a wounded sparrow in winter"),
    ("contentment", "a dog who loses his bone chasing a reflection"),
    ("wisdom over strength", "a clever mouse who frees a trapped lion"),
    ("keeping promises", "a prince who gives his word to a humble farmer"),
]

_PROMPT_TEMPLATE = """You are the head writer for a faceless YouTube channel called
"{channel}" that publishes ONE long, heartwarming MORAL STORY FOR CHILDREN
every day. The audience is families in the USA. The narration is read aloud by
a single warm, gentle storyteller voice.

Write ONE complete story of about {words} words. LENGTH IS IMPORTANT: it must
be AT LEAST 4 minutes when read aloud (~650 words) and at most 7 minutes
(~1000 words). Do NOT write a short story - develop the scenes fully. Follow
ALL of these rules:

HOOK (very important):
- The first 1-2 sentences MUST be an irresistible hook that makes the viewer
  stop and stay (a question, a promise, or a tiny mystery). Example styles:
  "What would you do if you found a bag of gold that wasn't yours?" or
  "Nobody in the village believed the smallest boy could do it - until that
  morning." Make it fresh and specific to THIS story.

RETENTION:
- Tell the story in clear, simple, vivid language a 7-year-old can follow.
- Use short scenes with a clear beginning, a problem, rising tension, a turning
  point, and a satisfying ending.
- Every minute or so, add a small "open loop" or cliffhanger line that makes
  the listener want to keep going (e.g. "But what happened next, no one
  expected.").
- Keep sentences fairly short and easy to narrate. No tongue-twisters.

MORAL:
- The story must clearly teach the lesson: {lesson}.
- Near the end, state the moral plainly in one clean sentence starting with
  "The moral of the story is".

EMOTION (very important):
- Make the story genuinely HEART-TOUCHING - warm, emotional, the kind that
  gives a gentle lump in the throat or happy tears by the end - while staying
  simple and wholesome for children. Build a real emotional connection with the
  main character so the ending truly lands.

CLOSE:
- End with this exact spoken call to action: "{cta}"

FORMAT:
- Plain spoken sentences only. No emojis, no stage directions, no markdown, no
  chapter headings, no hashtags, no quotation marks around the whole thing.
  American English.
- Do NOT use brand names or real people.

The story should be about: {topic}

Return ONLY a JSON object (no code fences) with these keys:
  "title": a short, curiosity-driven title (max 9 words, no quotes),
  "hook": the single opening hook sentence (used for the thumbnail too),
  "moral": the one-sentence moral,
  "main_character": a SHORT fixed visual description of the main character so
          they look the SAME in every scene, e.g. "a 7-year-old boy with messy
          black hair, a red shirt and bare feet" or "a small fluffy brown
          puppy with a white patch". Keep it concrete and consistent.
  "text": the FULL narration as one string (including the hook at the start
          and the call to action at the end),
  "scenes": an array of 10-14 SHORT visual descriptions, IN STORY ORDER, one per
          key beat of the story. Each MUST describe the CHARACTERS + setting +
          action of that moment so an illustrator could draw it, e.g.
          "a poor young boy in torn clothes crying beside a forest river at
          dawn", "a kind old woman handing bread to a hungry child". Keep each
          to a single vivid sentence. NO text/words in the scene.
  "keywords": an array of 5-8 short stock-footage search phrases that match the
          SETTING and ACTION of the story (e.g. "forest path sunlight",
          "child running village", "old man smiling"). Describe scenery and
          gentle human/nature action - NEVER request real brands or text.
"""


@dataclass
class Story:
    title: str
    text: str
    hook: str = ""
    moral: str = ""
    keywords: list = field(default_factory=list)
    scenes: list = field(default_factory=list)
    main_character: str = ""

    def __post_init__(self):
        if not self.keywords:
            self.keywords = list(get_cfg("pexels.default_keywords", []))
        if not self.hook:
            parts = re.split(r"(?<=[.!?])\s+", self.text.strip(), maxsplit=1)
            self.hook = parts[0] if parts else self.title
        if not self.scenes:
            self.scenes = derive_scenes_from_text(self.text)

    @property
    def word_count(self):
        return len(self.text.split())


def derive_scenes_from_text(text, target=12):
    """Fallback: split the narration into ~target visual scene prompts so AI
    images can still be generated when the model didn't return a 'scenes' list
    (e.g. the bundled fallback stories)."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s.strip()]
    if not sentences:
        return []
    target = max(4, min(target, len(sentences)))
    per = max(1, len(sentences) // target)
    scenes = []
    for i in range(0, len(sentences), per):
        chunk = " ".join(sentences[i : i + per]).strip()
        if chunk:
            scenes.append(chunk)
        if len(scenes) >= target:
            break
    return scenes


def _build_prompt(lesson, topic):
    return _PROMPT_TEMPLATE.format(
        channel=get_cfg("channel.name", "MoralTales"),
        words=get_cfg("story.target_words", 950),
        lesson=lesson,
        topic=topic,
        cta=get_cfg("channel.cta", "Subscribe for a new moral story every day!"),
    )


def _parse_model_json(raw):
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except Exception:
        return None


def _gemini_keys():
    """All configured Gemini keys, in order. Add GEMINI_API_KEY_2 / _3 (fresh
    free keys from other Google accounts) to survive the daily free quota."""
    keys = []
    for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        v = get_env(name)
        if v and v not in keys:
            keys.append(v)
    return keys


def _generate_with_gemini(lesson, topic):
    keys = _gemini_keys()
    if not keys:
        log.warning("GEMINI_API_KEY not set - using local stories.json fallback.")
        return None
    try:
        import google.generativeai as genai
    except Exception as exc:
        log.warning("google-generativeai not available (%s); using fallback.", exc)
        return None

    default_model = get_env("GEMINI_MODEL", get_cfg("gemini.model", "gemini-2.0-flash"))
    candidates = get_cfg("gemini.model_candidates", ["gemini-2.0-flash"])
    ordered = [default_model] + [m for m in candidates if m != default_model]

    prompt = _build_prompt(lesson, topic)
    temperature = get_cfg("gemini.temperature", 0.95)
    min_words = int(get_cfg("story.min_words", 750))

    for ki, key in enumerate(keys, 1):
        try:
            genai.configure(api_key=key)
        except Exception as exc:
            log.warning("Could not configure Gemini key #%d (%s); trying next key.", ki, exc)
            continue
        log.info("Trying Gemini key #%d of %d ...", ki, len(keys))
        for model_name in ordered:
            try:
                log.info("Requesting story from Gemini model '%s' (key #%d)...", model_name, ki)
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(
                    prompt, generation_config={"temperature": temperature}
                )
                raw = getattr(resp, "text", None)
                data = _parse_model_json(raw)
                if not data or not data.get("text"):
                    log.warning("Model '%s' returned no usable text; trying next.", model_name)
                    continue
                story = Story(
                    title=str(data.get("title") or "A Moral Story").strip(),
                    text=str(data["text"]).strip(),
                    hook=str(data.get("hook") or "").strip(),
                    moral=str(data.get("moral") or "").strip(),
                    keywords=[str(k).strip() for k in data.get("keywords", []) if str(k).strip()],
                    scenes=[str(s).strip() for s in data.get("scenes", []) if str(s).strip()],
                    main_character=str(data.get("main_character") or "").strip(),
                )
                cta = get_cfg("channel.cta", "")
                if cta and cta.lower() not in story.text.lower():
                    story.text = story.text.rstrip() + " " + cta
                if story.word_count < min_words:
                    log.warning(
                        "Model '%s' story too short (%d words); trying next.",
                        model_name, story.word_count,
                    )
                    continue
                log.info("Gemini story ready via '%s' key #%d (%d words).", model_name, ki, story.word_count)
                return story
            except Exception as exc:
                log.warning("Gemini key #%d model '%s' failed (%s); trying next.", ki, model_name, exc)
                continue
        log.warning("Gemini key #%d exhausted/failed; trying next key.", ki)

    log.warning("All Gemini keys/models failed (likely daily quota) - using local stories.json.")
    return None


# --------------------------------------------------------------------------
# Local fallback
# --------------------------------------------------------------------------
def load_fallback_stories():
    try:
        with open(STORIES_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        items = data.get("stories", []) if isinstance(data, dict) else data
        stories = []
        for item in items:
            try:
                stories.append(
                    Story(
                        title=str(item.get("title", "A Moral Story")),
                        text=str(item["text"]),
                        hook=str(item.get("hook", "")),
                        moral=str(item.get("moral", "")),
                        keywords=list(item.get("keywords", [])),
                        scenes=list(item.get("scenes", [])),
                        main_character=str(item.get("main_character", "")),
                    )
                )
            except Exception:
                continue
        return stories
    except Exception as exc:
        log.error("Could not load stories.json (%s).", exc)
        return []


def _fallback_story():
    stories = load_fallback_stories()
    if stories:
        return random.choice(stories)
    return Story(
        title="The Honest Woodcutter",
        text=(
            "What would you do if a stranger offered you gold you did not earn? "
            "A poor woodcutter once dropped his only axe into a deep river. As he "
            "wept, a shining spirit rose from the water holding an axe of pure gold. "
            "Is this yours, she asked. No, the woodcutter said, mine was only old "
            "iron. Pleased by his honesty, the spirit gave him the gold axe and the "
            "iron one too. The moral of the story is that honesty is always "
            "rewarded in the end. Subscribe for a new moral story every day!"
        ),
        moral="Honesty is always rewarded in the end.",
        keywords=["forest river sunlight", "old man working", "calm water nature"],
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def generate_story(lesson=None, topic=None):
    """Return a single Story, preferring Gemini, falling back to stories.json."""
    if not lesson or not topic:
        lesson, topic = random.choice(TOPIC_POOL)
        log.info("Auto-picked lesson: %s | topic: %s", lesson, topic)
    story = _generate_with_gemini(lesson, topic)
    if story is None:
        story = _fallback_story()
        log.info("Using fallback story: '%s'.", story.title)
    return story
