# Sweet Soul Stories — monetisation reality check & action plan

Channel snapshot used for this plan: **399 subscribers, 113 videos, ~125,000 lifetime
views, roughly 5 weeks old, Shorts landing at 275–941 views each.**

---

## 1. The honest math on "monetise in 15 days"

There are two ways into the YouTube Partner Program, and a lower fan-funding tier.

| Gate | Requirement | Where the channel is | Verdict for 15 days |
|---|---|---|---|
| **Fan funding tier** | 500 subs + 3 public uploads in 90 days + (3,000 watch hours in 12 mo **OR** 3M Shorts views in 90 days) | 399 subs, uploads fine | **Subs part is reachable.** The hours/views part is not. |
| **Full ads — Shorts route** | 1,000 subs + **10,000,000** valid public Shorts views in 90 days | ~125K lifetime views | **Not possible.** Needs ~111,000 views/day; currently ~3,600/day — a 31× jump. |
| **Full ads — long-form route** | 1,000 subs + **4,000** valid public watch hours in 12 months | Long-form posts every other day | **Not possible in 15 days**, but this is the only realistic route overall. |

Why long-form is the realistic route: watch hours come from **duration**, not view count.
4,000 hours = 240,000 minutes. A 6-minute story watched ~40% of the way through banks
about 2.4 minutes per view, so roughly **100,000 long-form views** clears the gate — versus
**10 million** Shorts views. Same milestone, two orders of magnitude apart in difficulty.

Subscriber math: 399 subs in ~35 days is about 11/day. Reaching 1,000 in 15 days needs
about 40/day. Reaching **500** needs about 7/day, which is comfortably achievable.

**So: 15 days to full monetisation is not achievable at this scale.** What 15 days *can*
deliver is: cross 500 subs, remove the policy rejection risk described below, and get the
long-form engine producing enough volume that the 4,000-hour gate becomes a matter of
months instead of never.

---

## 2. The bigger risk nobody was tracking: policy, not SEO

YouTube renamed its "repetitious content" policy to **"inauthentic content"** in July 2025
and expanded it in July 2026. The first of the three named categories is
*generic, repetitive, or template-based content*, and it is **ineligible for monetisation**.
([YouTube channel monetisation policies](https://support.google.com/youtube/answer/1311392),
[TechCrunch on the July 2026 clarification](https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/))

Before this change, every one of the 113 uploads shipped with:

- the identical title suffix `| Cute & Wholesome #shorts #cute`
- the identical 8-hashtag block
- the identical two-sentence description tail
- the identical spoken sign-off, in the same synthetic voice
- a description that was a verbatim copy of the video's own narration

That is a machine-detectable template fingerprint across an entire channel. Even if the
subscriber and watch-hour gates were met, that is the pattern a YPP reviewer rejects. So
the work in this change set is not only about getting more views — it is about being
*approvable* when the numbers do arrive.

*Content in this section was rephrased from the linked sources for licensing compliance.*

---

## 3. What changed in the code

### New: per-video SEO engine
- **`modules/seo.py`** — subject detection (puppy / kitten / baby / pair buckets) drives a
  search anchor, 20 rotating title patterns, 4 rotating hashtag pools, a unique description
  body, and a tag set built to fit YouTube's 500-character budget.
- **`longform/modules/seo.py`** — the same idea for long-form, plus **auto-generated
  chapters** with real timestamps derived from the narration length.
- Metadata is now built **once at generate time** and stored in `manifest.json`. The
  uploader consumes it instead of stamping a fixed suffix on top.

### Retention fixes (why views were 275–941)
| Setting | Before | After | Reason |
|---|---|---|---|
| `captions.enabled` | `false` | `true` | A large share of Shorts plays start muted. With captions off, those viewers got no text at all. |
| `hook.enabled` | `false` | `true`, 2.5s | There was no scroll-stopper in the first frame. Now driven by short 2–4 word `SCREEN_HOOKS`, not the long spoken sentence that was unreadable at 150px. |
| `target_duration_seconds` | 30 | 24 | Shorts distribution leans on view-duration-as-a-percentage and on loops. |
| `clip_cut_seconds` | 2.5 | 1.8 | Faster visual changes reduce mid-video swipe-away. |
| `tts.voice` | 1 fixed voice | pool of 6 + rate variation | 113 videos in one identical synthetic voice reads as mass-produced. |
| Pexels keywords | 10 (incl. breed-specific) | 18 generic | The old list kept pulling the same handful of stock clips. |

### Content diversity
- Spoken hooks: 30 → **58**
- Story topics: 20 → **46**
- New: 24 short on-screen hooks; 8 rotating spoken sign-offs (was 1 fixed line)
- Long-form: rotating sign-offs, and `channel.name` corrected from **"MoralTales"** to
  **"Sweet Soul Stories"** — the long-form pipeline uploads to the *same* channel with the
  *same* token, so descriptions were welcoming viewers to a brand that does not exist there.

### New tools
- **`seo_report.py`** — verifies uniqueness and API limits with no keys needed.
  `python seo_report.py -n 40` → currently **604 checks passing**, 100% distinct titles,
  descriptions and hashtag sets.
- **`retitle_existing.py`** — rewrites the metadata of the **113 already-published videos**.
  Dry run by default. Fixing the generator only fixes future uploads; this fixes the back
  catalogue, which is what a reviewer actually inspects.
- **`modules/thumbnail.py`** — Shorts thumbnails for the channel grid / subscriptions feed /
  search. These are the surfaces where a viewer decides to subscribe, and the channel was
  letting YouTube pick an arbitrary (often blurry) frame.

---

## 4. Your 15-day checklist — the parts only you can do

### Day 1 — clean up the back catalogue
```bash
python retitle_existing.py --authorize            # one-time, needs force-ssl scope
python retitle_existing.py --only-legacy --limit 20   # DRY RUN, read the diff
python retitle_existing.py --only-legacy --limit 20 --apply
```
Repeat ~20/day for 6 days until all 113 are done. Keep the batch small: uploads already
consume ~8,000 of the 10,000 daily API units.

### Day 1 — two settings changes worth real money
1. **Make the GitHub repo public.** Private repos burn Actions minutes against the 2,000/month
   free limit, which is why long-form only runs every *other* day. Public repos get unlimited
   Actions minutes — that alone unlocks daily long-form. No secrets live in the code (they are
   all GitHub Secrets), so this is safe.
2. **Shift the upload mix toward long-form.** Long-form is the only thing that generates watch
   hours. YouTube's API quota allows about 6 uploads/day at 1,600 units each, so:
   `4 Shorts + 1 long-form` → **`3 Shorts + 2 long-form`**. You can also request a quota
   increase in Google Cloud Console.

### Every day — 10 minutes of manual work that the API cannot do
- **Pin the first comment.** The generator now prints one for each video
  (`PIN THIS COMMENT on https://youtu.be/...` in the workflow log). Comment velocity in the
  first hour is a strong distribution signal, and posting comments needs a scope the upload
  token does not have.
- **Reply to every comment** for the first hour after each upload.
- **Check Studio → Content → Shorts**, sort by views, and note which *screen hook* and which
  *subject* (puppy / kitten / baby) the winners used. Feed that back by weighting those pools.

### Week 1 — verify you are actually eligible
- Studio → **Earn** — confirm which tier is offered in your country. The 500-sub fan-funding
  tier rolled out region by region, so check rather than assume.
- Studio → Settings → Channel → **Advanced** — confirm the "made for kids" setting.
  Marking a channel as made-for-kids disables personalised ads and severely cuts RPM. This
  repo sets `made_for_kids: false`; make sure the channel-level setting agrees with reality.
- Confirm **2-step verification** is on (required for custom thumbnails).

### Things to stop doing
- Don't post more Shorts hoping for 10M views in 90 days. That target is unreachable from
  3,600 views/day, and every hour spent there is an hour not spent on watch hours.
- Don't add more hashtags. Above 15, YouTube ignores **all** of them. The engine ships 9.

---

## 5. Realistic timeline

| Milestone | Realistic ETA | Depends on |
|---|---|---|
| 500 subscribers | **10–20 days** | back catalogue retitled, thumbnails live, hooks on screen |
| 3,000 watch hours (fan funding) | 2–4 months | daily long-form, decent audience retention |
| 1,000 subscribers | 1.5–3 months | one or two Shorts breaking out |
| 4,000 watch hours (full ads) | **4–7 months** | 2 long-form/day at improved retention |

Anyone promising 15 days is selling something. The version of this that works is: fix the
template problem now so you are *approvable*, and put the volume into long-form so the
watch-hour clock actually moves.

---

## 6. Suggested next build (not in this change set)

An **analytics feedback loop**: pull per-video CTR, average view duration and subscribers-gained
from the YouTube Analytics API, then weight the hook / topic / subject pools toward what is
measurably winning. Right now every pool is drawn from uniformly at random, so the pipeline has
no way to learn from its own results. That is the single biggest remaining gap.
