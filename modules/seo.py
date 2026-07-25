"""
SEO / metadata engine for SweetSoul Stories (YouTube Shorts).

WHY THIS MODULE EXISTS
----------------------
Before this module, every single reel was published with:

    title       = f"{base} | Cute & Wholesome #shorts #cute"
    description = full narration text + the same 2 boilerplate sentences
    hashtags    = "#shorts #cute #puppy #baby #aww #animals #wholesome #heartwarming"
    tags        = script keywords + the same 14 config tags

That means 100+ videos shipped with a byte-identical title suffix, an identical
hashtag block and an identical description tail. Two bad consequences:

  1. ALGORITHM: YouTube cannot tell the videos apart. Search/browse impressions
     cannibalise each other because every video targets the exact same query
     set, and the duplicate suffix eats the visible title space where the
     click-driving words should be.
  2. POLICY: YouTube's "inauthentic content" policy (renamed from "repetitious
     content" in July 2025, expanded July 2026) explicitly calls out
     "generic, repetitive, or template-based content" as ineligible for
     monetisation. A perfectly templated metadata fingerprint across a whole
     channel is the single easiest thing for an automated reviewer to detect.

So this module builds metadata that is DIFFERENT for every upload while still
being keyword-targeted:

  * build_title()        - search anchor first, rotating emotional pattern,
                           no fixed suffix, no "#shorts" spam.
  * build_description()  - unique opening line, real story teaser (not the whole
                           narration dumped verbatim), an engagement question,
                           a rotating CTA, a natural keyword paragraph, and a
                           per-video hashtag set.
  * build_tags()         - subject-aware tag set, deduped, trimmed to YouTube's
                           500-character total budget.
  * build_hashtags()     - 8-10 rotating hashtags drawn from 4 different pools.
  * build_pinned_comment() - the first-comment text that drives replies.

Everything is pure-python and dependency-free so it can be unit-checked with
`python seo_report.py` without any API keys or media libraries.
"""

import logging
import random
import re

from .config import get_cfg

log = logging.getLogger("sweetsoul.seo")


# ==========================================================================
# 1. Subject detection
# ==========================================================================
# The whole point of subject detection is that a puppy video and a baby video
# should NOT be pushed to the same keyword set. Different search demand,
# different audience, different hashtags.

_TOKEN_PATTERNS = {
    "dog": r"\b(puppy|puppies|pup|pups|dog|dogs|doggo)\b",
    "cat": r"\b(kitten|kittens|kitty|cat|cats)\b",
    # "newborn" is deliberately NOT here: "newborn kitten" and "newborn puppy"
    # are common phrases in this niche and would score a human baby that the
    # video never contains.
    "baby": r"\b(baby|babies|toddler|toddlers|infant|child|children|kid|kids)\b",
}

# The title and the footage keywords describe what the video is actually ABOUT.
# The narration body does too, but its FIRST sentence is a randomly assigned
# generic hook ("This little puppy just became everyone's favorite hero.") which
# frequently names an animal the video does not contain -- that is what used to
# mislabel kitten videos as baby-and-dog videos. So: heavy weight on title and
# keywords, light weight on the body, and the hook sentence excluded entirely.
_W_TITLE = 3
_W_KEYWORDS = 3
_W_BODY = 1

# A single light-weight mention is not enough to claim a subject is present.
_PRESENCE_THRESHOLD = 2

DEFAULT_SUBJECT = "puppy_baby"

_PAIR_SUBJECTS = {
    frozenset(("dog", "baby")): "puppy_baby",
    frozenset(("cat", "baby")): "kitten_baby",
    frozenset(("dog", "cat")): "puppy_kitten",
}

_SOLO_SUBJECTS = {"dog": "puppy", "cat": "kitten", "baby": "baby"}


def _strip_hook_sentence(text):
    """Drop sentence 1, which is always a randomly assigned generic hook."""
    body = re.sub(r"\s+", " ", str(text or "").strip())
    parts = re.split(r"(?<=[.!?])\s+", body, maxsplit=1)
    return parts[1] if len(parts) == 2 else body


def detect_subject(title="", text="", keywords=None):
    """Classify a reel into one of the subject buckets.

    Scored rather than first-match: a passing mention in the narration can no
    longer outvote the title and the footage keywords. Getting this right
    matters because the subject decides the search anchor, the hashtag pool and
    the tag set -- a kitten video tagged "baby and dog best friends" is served to
    the wrong audience and gets swiped away, which then suppresses the next
    upload too.
    """
    sources = [
        (str(title or ""), _W_TITLE),
        (" ".join(str(k) for k in (keywords or [])), _W_KEYWORDS),
        (_strip_hook_sentence(text), _W_BODY),
    ]

    scores = {"dog": 0, "cat": 0, "baby": 0}
    for blob, weight in sources:
        low = blob.lower()
        for token, pattern in _TOKEN_PATTERNS.items():
            hits = len(re.findall(pattern, low))
            if hits:
                scores[token] += weight * min(hits, 3)

    present = [t for t, s in scores.items() if s >= _PRESENCE_THRESHOLD]

    if len(present) >= 2:
        # Keep the two strongest signals and map them to a pair bucket.
        top2 = sorted(present, key=lambda t: scores[t], reverse=True)[:2]
        return _PAIR_SUBJECTS.get(frozenset(top2), DEFAULT_SUBJECT)
    if len(present) == 1:
        return _SOLO_SUBJECTS[present[0]]

    # Nothing scored above the threshold: fall back to the strongest raw signal
    # before giving up on the channel default.
    best = max(scores, key=lambda t: scores[t])
    if scores[best] > 0:
        return _SOLO_SUBJECTS[best]
    return DEFAULT_SUBJECT


# ==========================================================================
# 2. Search anchors — the actual phrase people type into YouTube
# ==========================================================================
# These are the "head" keywords. One of them is placed at or near the FRONT of
# the title, because YouTube weights early title words more heavily and the
# Shorts player truncates the title after roughly 40-50 visible characters.

SEARCH_ANCHORS = {
    "puppy": [
        "Cute Puppy",
        "Funny Puppy",
        "Puppy Video",
        "Cutest Puppy",
        "Adorable Puppy",
        "Puppy Moments",
        "Rescue Puppy",
    ],
    "kitten": [
        "Cute Kitten",
        "Funny Cat",
        "Kitten Video",
        "Cutest Kitten",
        "Adorable Kitten",
        "Rescue Kitten",
        "Cat Moments",
    ],
    "baby": [
        "Cute Baby",
        "Funny Baby",
        "Baby Video",
        "Cutest Baby",
        "Adorable Baby",
        "Baby Moments",
        "Funny Toddler",
    ],
    "puppy_baby": [
        "Baby And Puppy",
        "Dog Meets Baby",
        "Cute Baby And Dog",
        "Puppy Loves Baby",
        "Baby And Dog Best Friends",
        "Dog And Baby Moments",
    ],
    "kitten_baby": [
        "Baby And Kitten",
        "Cat Meets Baby",
        "Cute Baby And Cat",
        "Kitten Loves Baby",
        "Baby And Cat Best Friends",
    ],
    "puppy_kitten": [
        "Puppy And Kitten",
        "Cat And Dog Friendship",
        "Kitten Meets Puppy",
        "Cute Cat And Dog",
        "Dog And Cat Best Friends",
    ],
}


# ==========================================================================
# 3. Title patterns
# ==========================================================================
# Each entry is a format string using {anchor} (the search phrase) and {core}
# (the Gemini-written story title). NOTE: deliberately no "#shorts" — YouTube
# classifies a Short by aspect ratio + duration, and a hashtag in the title
# just burns visible characters that could be selling the click.

TITLE_PATTERNS = [
    "{anchor}: {core}",
    "{core} | {anchor}",
    "{anchor} - {core}",
    "{core} 🥹 {anchor}",
    "{anchor} You Need To See: {core}",
    "This {anchor} Will Melt Your Heart | {core}",
    "{core} (Try Not To Smile) | {anchor}",
    "{anchor} | {core} ❤️",
    "Wait For The End 🥺 {core}",
    "{core} — And It Gets Better",
    "Nobody Expected This | {core}",
    "{core} | Wholesome {anchor}",
    "I Watched This 10 Times | {core}",
    "{anchor}: {core} 😭❤️",
    "The Internet Loves This {anchor} | {core}",
    "{core} | Best {anchor} Of The Day",
    "You'll Watch This Twice | {core}",
    "{core} 💕 {anchor} Moment",
    "This Is Why We Love {anchor}s | {core}",
    "{core} | Daily Dose Of Cute",
]

# Titles longer than this get the pattern decoration dropped so the searchable
# part survives. YouTube's hard cap is 100; ~72 keeps it readable in browse.
TITLE_SOFT_LIMIT = 72
TITLE_HARD_LIMIT = 100


def _clean_core(core):
    """Normalise the Gemini title: strip trailing punctuation, hashtags, quotes."""
    core = str(core or "").strip()
    core = re.sub(r"#\w+", "", core)          # no hashtags inside the core
    core = core.replace('"', "").replace("'", "'")
    core = re.sub(r"\s+", " ", core).strip()
    core = core.rstrip(".,;:-—|")
    # Drop the legacy hard-coded suffix if an old manifest entry still has it.
    core = re.sub(r"\s*\|\s*Cute\s*&\s*Wholesome.*$", "", core, flags=re.I).strip()
    return core or "A Little Moment Of Pure Joy"


def build_title(core_title, text="", keywords=None, subject=None, rng=None):
    """Compose one unique, search-anchored Shorts title.

    The anchor carries the search intent, the pattern carries the click
    emotion, and neither is fixed across uploads.
    """
    rng = rng or random
    core = _clean_core(core_title)
    subject = subject or detect_subject(core, text, keywords)
    anchor = rng.choice(SEARCH_ANCHORS.get(subject, SEARCH_ANCHORS["puppy_baby"]))
    pattern = rng.choice(TITLE_PATTERNS)

    title = pattern.format(anchor=anchor, core=core)

    # If decoration pushed us past the soft limit, fall back to the two
    # highest-value components only, then to the bare core.
    if len(title) > TITLE_SOFT_LIMIT:
        title = f"{anchor}: {core}"
    if len(title) > TITLE_SOFT_LIMIT:
        title = core
    return title[:TITLE_HARD_LIMIT].strip()


# ==========================================================================
# 4. Hashtags — four rotating pools
# ==========================================================================
# YouTube shows only the first 3 hashtags above the title, and IGNORES ALL
# hashtags on a video that has more than 15. We ship 8-10: enough for topical
# signal, few enough to stay clean and to differ between videos.

HASHTAG_CORE = ["#shorts", "#cute", "#wholesome", "#aww", "#feelgood", "#heartwarming"]

HASHTAG_SUBJECT = {
    "puppy": ["#puppy", "#puppylove", "#dogsofyoutube", "#cutedog", "#doglover", "#puppylife", "#rescuedog"],
    "kitten": ["#kitten", "#kittenlove", "#catsofyoutube", "#cutecat", "#catlover", "#kittenlife", "#rescuecat"],
    "baby": ["#cutebaby", "#babylove", "#toddler", "#babyvideos", "#babylaugh", "#funnybaby"],
    "puppy_baby": ["#babyanddog", "#puppy", "#cutebaby", "#dogandbaby", "#doglover", "#bestfriends"],
    "kitten_baby": ["#babyandcat", "#kitten", "#cutebaby", "#catandbaby", "#catlover", "#bestfriends"],
    "puppy_kitten": ["#puppyandkitten", "#catsanddogs", "#puppy", "#kitten", "#bestfriends", "#petlove"],
}

HASHTAG_EMOTION = [
    "#trynottosmile", "#melts", "#sweetmoments", "#purejoy", "#happytears",
    "#soothing", "#adorable", "#precious", "#mademysmile", "#dailydoseofcute",
]

HASHTAG_DISCOVERY = [
    "#animalshorts", "#cuteanimals", "#petshorts", "#viralshorts",
    "#satisfying", "#relaxing", "#familyfriendly", "#sweetsoulstories",
]


def build_hashtags(subject=None, rng=None, count=9):
    """Return a rotating, subject-aware hashtag list (order matters).

    Position 1-3 are the ones YouTube surfaces above the title, so we lead with
    one core tag + two subject tags: broad reach plus precise topicality.
    """
    rng = rng or random
    subject = subject or DEFAULT_SUBJECT
    subj_pool = HASHTAG_SUBJECT.get(subject, HASHTAG_SUBJECT["puppy_baby"])

    picked = []
    picked.append(rng.choice(HASHTAG_CORE))
    picked.extend(rng.sample(subj_pool, min(2, len(subj_pool))))
    picked.extend(rng.sample(HASHTAG_CORE, min(2, len(HASHTAG_CORE))))
    picked.extend(rng.sample(HASHTAG_EMOTION, min(2, len(HASHTAG_EMOTION))))
    picked.extend(rng.sample(HASHTAG_DISCOVERY, min(2, len(HASHTAG_DISCOVERY))))

    # "#shorts" must survive dedupe, everything else is order-preserved unique.
    unique = list(dict.fromkeys(picked))
    if "#shorts" not in unique:
        unique.insert(0, "#shorts")
    return unique[: max(3, int(count))]


# ==========================================================================
# 5. Tags (the hidden keyword field)
# ==========================================================================
# YouTube's limit is 500 characters TOTAL across all tags (commas count).
# Tags are a weak ranking signal these days but they still help YouTube
# understand a brand-new upload with no watch data, which is exactly our case.

TAG_EVERGREEN = [
    "cute animals", "wholesome", "heartwarming", "feel good video",
    "cute animal video", "try not to smile", "animal shorts", "cute shorts",
]

TAG_SUBJECT = {
    "puppy": ["cute puppy", "puppy video", "funny puppy", "puppies", "cute dog",
              "dog video", "rescue puppy", "puppy and owner", "adorable puppy"],
    "kitten": ["cute kitten", "kitten video", "funny cat", "kittens", "cute cat",
               "cat video", "rescue kitten", "kitten playing", "adorable kitten"],
    "baby": ["cute baby", "funny baby", "baby video", "toddler video",
             "baby laughing", "cute babies", "funny toddler", "adorable baby"],
    "puppy_baby": ["baby and dog", "baby and puppy", "dog meets baby",
                   "cute baby and dog", "dog and baby best friends",
                   "puppy loves baby", "baby with pet", "kids and dogs"],
    "kitten_baby": ["baby and cat", "baby and kitten", "cat meets baby",
                    "cute baby and cat", "cat and baby best friends",
                    "kitten loves baby", "baby with pet", "kids and cats"],
    "puppy_kitten": ["puppy and kitten", "cat and dog", "cat and dog friendship",
                     "kitten meets puppy", "cats and dogs playing",
                     "pet best friends", "cute pets"],
}

TAGS_CHAR_BUDGET = 480  # a little under 500 so we never get a 400 from the API
TAG_MAX_LEN = 60        # single overlong tag = wasted budget


def _normalise_tag(tag):
    tag = re.sub(r"\s+", " ", str(tag or "").strip().lower())
    tag = tag.strip(",")
    return tag[:TAG_MAX_LEN]


def build_tags(core_title="", keywords=None, subject=None, rng=None, extra=None):
    """Build a deduped tag list that fits inside YouTube's 500-char budget.

    Order = most specific first, because that is what survives the trim.
    """
    rng = rng or random
    subject = subject or DEFAULT_SUBJECT

    candidates = []
    # 1. Long-tail from the actual video title (most specific signal we have).
    core = _clean_core(core_title).lower()
    if core:
        candidates.append(core)
    # 2. Gemini's footage keywords describe what is literally on screen.
    candidates.extend(keywords or [])
    # 3. Subject head terms.
    subj = list(TAG_SUBJECT.get(subject, TAG_SUBJECT["puppy_baby"]))
    rng.shuffle(subj)
    candidates.extend(subj)
    # 4. Channel-wide evergreen terms.
    ever = list(TAG_EVERGREEN)
    rng.shuffle(ever)
    candidates.extend(ever)
    # 5. Anything the caller wants to force in (e.g. config default_tags).
    candidates.extend(extra or [])

    tags = []
    used = set()
    budget = 0
    for raw in candidates:
        tag = _normalise_tag(raw)
        if not tag or tag in used:
            continue
        cost = len(tag) + 1  # +1 for the separating comma
        if budget + cost > TAGS_CHAR_BUDGET:
            continue
        tags.append(tag)
        used.add(tag)
        budget += cost
    return tags


# ==========================================================================
# 6. Description
# ==========================================================================
# Only the first ~150 characters show in search results and above the "more"
# fold, so line 1 must be a real sentence containing the target keyword. The
# rest exists to (a) give YouTube topical context and (b) drive engagement,
# which is the signal that actually moves Shorts distribution.

DESC_OPENERS = [
    "{anchor} alert: {teaser}",
    "{teaser} This is the kind of {anchor_lc} moment that makes your whole day better.",
    "Some days you just need a {anchor_lc} video like this. {teaser}",
    "{teaser} Watch it twice — the second time is even sweeter.",
    "If you needed a reason to smile today, here it is. {teaser}",
    "{teaser} Pure, simple, wholesome joy in under a minute.",
    "This one melted us. {teaser}",
    "{anchor} moments like this are why the internet is worth it. {teaser}",
]

DESC_QUESTIONS = [
    "Which part made you smile the most? Tell us in the comments 👇",
    "Did this make you smile? Drop a ❤️ in the comments so we know!",
    "Would your pet do the same thing? Tell us below 👇",
    "Comment 🐾 if you watched this more than once.",
    "Who else needed this today? Say hi in the comments 👋",
    "Tag someone who needs to see this right now.",
    "On a scale of 1-10, how cute was that? Comment your score!",
    "What should we call this little one? Best comment wins 🏆",
]

DESC_CTAS = [
    "Subscribe to SweetSoul Stories for a new heartwarming moment every single day.",
    "Hit subscribe — we post a fresh dose of cute daily, and you don't want to miss tomorrow's.",
    "New wholesome story every day. Subscribe so the next one finds you.",
    "If this made your day, subscribing takes two seconds and keeps them coming.",
    "Follow SweetSoul Stories for daily feel-good animal and baby moments.",
    "Subscribe for your daily dose of joy — one small, sweet story at a time.",
]

DESC_ABOUT = [
    "SweetSoul Stories collects the small, gentle moments between animals and the people "
    "who love them — first meetings, rescue days, naps, and the quiet friendships that "
    "form in between.",
    "This channel is a soft corner of the internet: short, kind stories about puppies, "
    "kittens, babies and the bonds they build. No noise, no drama, just warmth.",
    "We tell tiny heartwarming stories about pets and children — the kind that remind you "
    "how much love can fit into a very small moment.",
    "SweetSoul Stories is here for the days you need something gentle. Wholesome animal "
    "and baby moments, narrated with care, a few minutes at a time.",
]

# Shown as a plain, honest production note. Transparency about how the video is
# made is cheap to add and it is exactly the kind of signal that helps a human
# reviewer see the channel as an authentic production rather than scraped media.
PRODUCTION_NOTE = (
    "About this video: original narration written and produced for SweetSoul Stories, "
    "paired with licensed royalty-free footage and music."
)


def _teaser(text, max_chars=150):
    """First 1-2 sentences of the narration, NOT the whole script.

    Dumping the full narration into the description (the old behaviour) gave
    every video a description that was a verbatim duplicate of its own audio and
    added zero new keywords. A short teaser keeps the curiosity gap intact.
    """
    body = re.sub(r"\s+", " ", str(text or "").strip())
    if not body:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", body)
    # Sentence 1 of every script is the generic spoken hook ("Wait for it...",
    # "You won't believe..."). It carries zero keywords, so using it as the
    # description opener would waste the only line that shows in search results.
    if len(sentences) >= 3:
        sentences = sentences[1:]
    out = ""
    for s in sentences:
        if len(out) + len(s) + 1 > max_chars and out:
            break
        out = (out + " " + s).strip()
    return out


def build_description(
    core_title="",
    text="",
    keywords=None,
    subject=None,
    hashtags=None,
    rng=None,
    channel_url=None,
):
    """Compose a unique, keyword-front-loaded Shorts description."""
    rng = rng or random
    subject = subject or detect_subject(core_title, text, keywords)
    anchor = rng.choice(SEARCH_ANCHORS.get(subject, SEARCH_ANCHORS["puppy_baby"]))
    teaser = _teaser(text)

    opener = rng.choice(DESC_OPENERS).format(
        anchor=anchor, anchor_lc=anchor.lower(), teaser=teaser
    ).strip()

    # A natural-language keyword line. Written as prose on purpose: a bare
    # comma-separated keyword dump reads as spam to both viewers and reviewers.
    kw = [_normalise_tag(k) for k in (keywords or []) if str(k).strip()]
    kw_line = ""
    if kw:
        kw_line = "In this Short: " + ", ".join(kw[:5]) + "."

    parts = [
        opener,
        kw_line,
        rng.choice(DESC_QUESTIONS),
        rng.choice(DESC_CTAS),
        rng.choice(DESC_ABOUT),
        PRODUCTION_NOTE,
    ]
    if channel_url:
        parts.insert(4, f"More stories like this: {channel_url}")

    body = "\n\n".join(p for p in parts if p)

    tags_line = " ".join(hashtags or build_hashtags(subject, rng=rng))
    full = f"{body}\n\n{tags_line}".strip()
    return full[:4900]


# ==========================================================================
# 7. Pinned first comment
# ==========================================================================
# A pinned comment posted by the channel is one of the cheapest ways to start
# a comment thread, and comment velocity in the first hour is a strong Shorts
# distribution signal. Requires the youtube.force-ssl scope to automate; the
# text is generated here either way so it can be posted manually.

PINNED_COMMENTS = [
    "Okay but the part at the end though 🥹 What was your favourite second?",
    "We watched this 6 times before uploading it. Sorry not sorry 🐾",
    "Genuine question: who is cuter here? Reply with your pick 👇",
    "If this made you smile, that's all we wanted today ❤️",
    "Tell us in one word how this made you feel 👇",
    "Fun fact: this took 40 takes of nothing happening before THIS happened 😅",
    "Tag the person who always sends you cute animal videos.",
    "Comment 🐾 and we'll reply to every single one today.",
]


def build_pinned_comment(rng=None):
    rng = rng or random
    return rng.choice(PINNED_COMMENTS)


# ==========================================================================
# 8. One-call entry point
# ==========================================================================
def build_metadata(core_title, text="", keywords=None, rng=None):
    """Return the full metadata bundle for one reel.

    Called once at GENERATE time and stored in manifest.json, so the uploader
    never re-derives (and never re-appends) anything. That is what removed the
    duplicated "| Cute & Wholesome #shorts #cute" suffix.
    """
    rng = rng or random
    subject = detect_subject(core_title, text, keywords)

    hashtags = build_hashtags(subject, rng=rng, count=int(get_cfg("seo.hashtag_count", 9)))
    title = build_title(core_title, text, keywords, subject=subject, rng=rng)
    description = build_description(
        core_title=core_title,
        text=text,
        keywords=keywords,
        subject=subject,
        hashtags=hashtags,
        rng=rng,
        channel_url=get_cfg("seo.channel_url", None),
    )
    tags = build_tags(
        core_title=core_title,
        keywords=keywords,
        subject=subject,
        rng=rng,
        extra=get_cfg("youtube.default_tags", []),
    )

    meta = {
        "subject": subject,
        "youtube_title": title,
        "youtube_description": description,
        "youtube_tags": tags,
        "hashtags": hashtags,
        "pinned_comment": build_pinned_comment(rng=rng),
    }
    log.info("SEO: subject=%s | title=%r | %d tags | %d hashtags",
             subject, title, len(tags), len(hashtags))
    return meta
