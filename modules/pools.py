"""
Content pools for SweetSoul Stories.

WHY THIS FILE EXISTS
--------------------
Everything a viewer can notice repeating lives here, in one place, so it can be
grown without touching pipeline logic. The pools used to sit inline in
gemini_script.py and were small enough that at 5 uploads a day a viewer would
meet the same story idea and the same spoken opener within a few days:

    story topics   46  ->  150     (1 per reel  -> ~30 days at 5 reels/day)
    spoken hooks   58  ->  120     (1 per reel  -> ~24 days)
    screen hooks   24  ->   80     (1 per reel  -> ~16 days)
    flash phrases   -  ->  152     (3 per reel  -> ~10 days)  NEW
    sign-offs       8  ->   45     (1 per reel  -> ~9 days)

Run `python modules/pools.py` to print the sizes and catch duplicates.

Size alone is not enough, though. Selection used to be `random.choice`, which
puts the item straight back in the bag, so a 150-item pool still produces
collisions within days. modules/history.py handles that: it records what has been
used and only ever offers unused items until a pool is genuinely exhausted.

Together: 150 topics at 5 videos/day means no story idea repeats for a full
month, and when the pool does cycle, the hook, screen hook, flash text, narrator
voice and title pattern will all be different anyway.
"""

# ==========================================================================
# STORY TOPICS  (150)
# ==========================================================================
# One is drawn per reel and handed to Gemini as the premise. Kept concrete and
# visual, because vague premises produce vague scripts.
TOPIC_POOL = [
    # --- first meetings (1-15) ---
    "a puppy meeting a baby for the first time",
    "a kitten and puppy becoming best friends",
    "a dog meeting his new baby sibling at the hospital",
    "a rescue dog meeting the child who chose him",
    "a kitten meeting the family's old gentle dog",
    "a baby meeting the family cat through a glass door",
    "a puppy meeting his reflection and deciding to make friends",
    "two rescue kittens meeting on their first day home",
    "a toddler meeting a litter of newborn puppies",
    "a shy cat meeting a crawling baby for the first time",
    "a puppy meeting a duckling in the backyard",
    "a baby meeting a giant gentle dog and reaching out",
    "a kitten meeting the household's grumpy older cat",
    "a rescue puppy meeting his new brother, a three-legged dog",
    "a toddler meeting the puppy she has been drawing for weeks",

    # --- rescue and adoption (16-32) ---
    "a rescue kitten finding a forever home",
    "a shy shelter dog wagging his tail for the very first time",
    "a senior dog getting adopted on his last day at the shelter",
    "a nervous rescue kitten finally purring after a month",
    "a three-legged puppy outrunning everyone at the park",
    "a one-eyed cat becoming the most confident pet in the house",
    "a stray puppy following a child home in the rain",
    "a kitten rescued from a drain pipe meeting her new family",
    "a deaf puppy learning hand signals from a patient toddler",
    "a rescue dog sleeping in a real bed for the first time",
    "a kitten who was the last one left at the shelter",
    "a scared puppy who hid for a week and then chose one person",
    "a blind kitten who learned the whole house by heart",
    "a rescue cat who finally let someone hold her",
    "a puppy found in a box who now has his own armchair",
    "an old cat adopted by a family with a newborn",
    "a rescue dog who guards the baby's door every night",

    # --- babies and toddlers (33-52) ---
    "a baby's first giggle triggered by a playful dog",
    "the way a baby laughs every time the dog sneezes",
    "a baby's first word being the family dog's name",
    "a baby's first steps guided by a loyal gentle dog",
    "a toddler teaching a puppy to sit",
    "a toddler carefully feeding a bottle to a rescued kitten",
    "a toddler reading a picture book to three sleepy puppies",
    "a toddler reading the alphabet out loud to a listening dog",
    "a toddler building a pillow fort for a shy puppy",
    "a toddler sharing an umbrella with a soaked stray cat",
    "a toddler and a fluffy cat playing hide and seek",
    "a toddler who insists the dog sits at the dinner table",
    "twin babies playing with a gentle giant dog",
    "a baby sharing snacks with a patient gentle dog",
    "a baby crawling across the room to reach a sleeping puppy",
    "a baby and a cat playing peekaboo through a doorway",
    "a baby falling asleep on a patient old dog's belly",
    "a toddler brushing a very tolerant cat",
    "a baby who claps every single time the dog walks in",
    "a toddler who packs the puppy a lunch for the park",

    # --- puppies being puppies (53-72) ---
    "a puppy discovering snow for the first time",
    "a puppy discovering rain and trying to bite it",
    "a puppy learning to swim with a laughing toddler cheering",
    "a puppy meeting the ocean for the first time",
    "a puppy who brings one sock to every visitor as a gift",
    "a puppy howling along to a baby's laughter",
    "a puppy who waits by the window every day for the school bus",
    "a puppy learning to climb stairs with an old dog's help",
    "a puppy's first birthday celebrated by the whole family",
    "a puppy who carries his blanket everywhere he goes",
    "a puppy who has decided the mailbox is his enemy",
    "a puppy trying to fit in a box three sizes too small",
    "a puppy learning that the vacuum is not actually a monster",
    "a puppy who falls asleep standing up mid-play",
    "a puppy discovering his own tail exists",
    "a puppy trying to carry a stick far too big for him",
    "a puppy who insists on sleeping in the cat's bed",
    "a puppy meeting a puddle and deciding to sit in it",
    "a puppy learning to fetch and bringing back the wrong thing",
    "a puppy who greets every single person on the morning walk",

    # --- kittens being kittens (73-92) ---
    "a kitten stealing a baby's toy and returning it",
    "a kitten discovering its own reflection for the first time",
    "a kitten who steals one strawberry every single morning",
    "a kitten learning to play fetch with a laughing toddler",
    "a kitten who insists on supervising bath time",
    "a kitten who sleeps in the fruit bowl and refuses to move",
    "a kitten who has claimed the warmest laundry basket",
    "a kitten trying to catch a sunbeam on the wall",
    "a kitten who yawns bigger than his own head",
    "a kitten meeting a bowl of water for the first time",
    "a kitten who hides in the same shoe every evening",
    "a kitten learning to jump and misjudging every distance",
    "a kitten who purrs only when the baby is nearby",
    "a kitten who adopted a litter of orphaned puppies",
    "a kitten who taught herself to open the cupboard",
    "a kitten fascinated by a dripping tap",
    "a kitten who tucks in a newborn baby every night",
    "a kitten who sits on the book every time someone reads",
    "a kitten meeting a feather and losing the fight",
    "a kitten who follows the toddler from room to room all day",

    # --- unlikely friendships (93-112) ---
    "a puppy and kitten cuddling under a warm blanket",
    "a cat and a dog sharing one very small sunbeam",
    "a puppy and a duckling that grew up in the same yard",
    "a kitten and a baby discovering bubbles together",
    "a dog and a rabbit who nap in the same basket",
    "a puppy who befriended the neighbour's shy cat over a fence",
    "a kitten and a parrot who taught each other to whistle",
    "a big dog letting three kittens use him as a bed",
    "a cat who grooms the puppy every morning without fail",
    "a dog and a tortoise racing very slowly across a lawn",
    "a puppy and a lamb who follow each other everywhere",
    "a kitten and an old dog who share one favourite chair",
    "a dog who adopted an abandoned kitten as his own",
    "a puppy and a goat who both think they are dogs",
    "a cat and a baby who both refuse to nap without the other",
    "two dogs who each wait for their own child at the gate",
    "a kitten and a puppy learning to share one water bowl",
    "a dog who lets the family cat win every single time",
    "a puppy who cries until the kitten comes to bed",
    "a cat and a dog who greet each other nose to nose every morning",

    # --- loyalty and quiet moments (113-132) ---
    "a dog gently guarding a sleeping newborn all night",
    "a dog carrying his blanket to a crying baby",
    "a cat who greets the baby at the door every single morning",
    "a dog proudly carrying his puppy to meet the family baby",
    "a toddler and puppy taking a nap together",
    "a toddler and a kitten sharing a single blanket in winter",
    "a dog who sits outside the bathroom door and waits every time",
    "a cat who sleeps on the pregnant owner's lap every evening",
    "a dog who walks the child to the school gate and back",
    "a puppy who will only sleep if he can hear someone breathing",
    "an old dog teaching a clumsy puppy how to be calm",
    "a cat who checks on every family member before sleeping",
    "a dog who brings his toy to whoever looks sad",
    "a kitten who sits on the windowsill until the car comes home",
    "a dog who has never once let the toddler wander off alone",
    "a cat who moved her kittens onto the child's bed",
    "a puppy who fell asleep holding the toddler's sleeve",
    "a dog who learned to be gentle only around the baby",
    "a cat who wakes the family at the exact same minute daily",
    "a dog who saved his own dinner to share with a stray",

    # --- seasons and small adventures (133-150) ---
    "a puppy's first autumn and a very large pile of leaves",
    "a kitten's first Christmas tree and a lot of poor decisions",
    "a baby and a puppy meeting their first butterfly",
    "a dog who swims in the lake every summer morning",
    "a kitten discovering a window box full of flowers",
    "a puppy's first car ride with his head out the window",
    "a toddler and a puppy jumping in the same puddle",
    "a kitten watching the first snowfall from a warm windowsill",
    "a baby and a dog sharing a picnic blanket in the garden",
    "a puppy's first trip to the beach and a war with the waves",
    "a kitten who hunts snowflakes through the glass",
    "a dog who insists on carrying the picnic basket himself",
    "a toddler and a kitten planting seeds in a tiny pot",
    "a puppy who discovered the garden sprinkler",
    "a baby and a puppy watching rain on the window together",
    "a kitten who claimed the freshly made bed as her own",
    "a dog and a toddler building the world's worst snowman",
    "a puppy who fell asleep in a basket of warm laundry",
]

# ==========================================================================
# SPOKEN HOOKS  (120)
# ==========================================================================
# The narrator's first sentence. Voice-only, never drawn on screen. These have
# to sound like a person talking, not like a headline.
HOOK_CANDIDATES = [
    # --- classic curiosity (1-20) ---
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

    # --- soft and emotional (21-40) ---
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

    # --- observational (41-60) ---
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
    "Look how carefully he does this. Nobody showed him how.",
    "It's the way he checks on her that gets me every time.",

    # --- warm and conversational (61-80) ---
    "Okay, you have to see what happens in about four seconds.",
    "I did not expect to cry over a puppy today, but here we are.",
    "Some moments are too small to photograph and too big to forget.",
    "This is a very short story about a very large heart.",
    "Every morning she does this. Every single morning.",
    "He is far too small to understand what he just did.",
    "This is going to be your favourite thirty seconds today.",
    "They have known each other for exactly one minute.",
    "Nobody in this house gets any work done anymore.",
    "This is the part of the day everyone waits for.",
    "It started with a sound at the door.",
    "She has been practising this all week.",
    "Watch his ears. That's when you'll know.",
    "This kind of thing does not happen twice.",
    "He picked her, not the other way around.",
    "There was no plan here. It just happened.",
    "Twenty seconds is all this takes. Give it to yourself.",
    "You will rewind this. I already know.",
    "This is a good day being made in real time.",
    "The best things really are the quiet ones.",

    # --- gentle and reflective (81-100) ---
    "Some friendships do not need words at all.",
    "This is what trust looks like when it is brand new.",
    "Nobody in the family remembers life before this.",
    "It only took one afternoon to change everything.",
    "She was the smallest one there, and the bravest.",
    "He had never had a soft place to sleep until now.",
    "This is the first time anyone has been gentle with him.",
    "Watch how she waits for him. She always waits.",
    "This is the sound of somebody being happy.",
    "One tiny decision, and two lives got better.",
    "He does not know he is being kind. He just is.",
    "There is nothing careful about this, and that is the beauty.",
    "It is the ordinary days that turn out to matter.",
    "This one is for anyone having a hard week.",
    "Nothing dramatic happens here. That's the point.",
    "This is a very small act of love, caught on camera.",
    "She has decided he belongs to her now.",
    "Home found him, not the other way around.",
    "The whole house went quiet when this happened.",
    "Two minutes earlier they were strangers.",

    # --- playful (101-120) ---
    "Absolutely nobody asked for this friendship, and yet.",
    "He has one plan, and it is a bad plan, and it is wonderful.",
    "This is going about as well as you'd expect.",
    "Confidence: enormous. Coordination: none.",
    "He believes he is enormous. He is not.",
    "She has never lost this game and she is not about to.",
    "This is the exact moment he realises what he has done.",
    "Nobody warned the cat about any of this.",
    "There is a right way to do this. He found another way.",
    "The plan was simple. The plan did not survive.",
    "He is very proud of himself and he should be.",
    "This is what happens when nobody is supervising.",
    "She has made a decision and there will be no discussion.",
    "One of them knows what is going on. It is not him.",
    "This took forty attempts. Here is attempt forty-one.",
    "He is trying so hard and it is going so badly.",
    "Watch him think about it. That's the best bit.",
    "This is the most serious thing that has ever happened to him.",
    "Somebody is about to be very surprised.",
    "It is not going to work, and he is going to try anyway.",
]

# ==========================================================================
# SCREEN HOOKS  (80)
# ==========================================================================
# Drawn on screen for the first ~2.5 seconds. Must be readable in one glance at
# arm's length, so 2-4 words maximum. This is the only hook a muted viewer gets.
SCREEN_HOOKS = [
    "WAIT FOR IT...", "WATCH TILL THE END", "TRY NOT TO SMILE", "THIS MELTED ME",
    "NOBODY EXPECTED THIS", "CUTEST THING TODAY", "GIVE IT 10 SECONDS", "THE ENDING THOUGH",
    "PURE JOY INCOMING", "SOUND ON 🔊", "HE JUST KNEW", "BEST FRIENDS ALREADY",
    "SHE HAD NO IDEA", "KEEP WATCHING", "TINY BUT MIGHTY", "THIS IS THE ONE",
    "WAIT FOR THE END 🥹", "IT GETS BETTER", "SMALL PAWS BIG HEART", "YOU'LL WATCH TWICE",
    "LOOK AT HIS FACE", "FIRST HELLO ❤️", "DON'T SCROLL PAST", "THE SOFTEST THING",
    "JUST WAIT 🥺", "WATCH HER EYES", "HE CHOSE HER", "DAY ONE AT HOME",
    "THIS IS NEW TO HIM", "NOBODY TAUGHT HIM", "STAY FOR 15 SECONDS", "ALMOST TOO CUTE",
    "SHE WAITED ALL DAY", "HIS FIRST TIME", "WATCH WHAT HE DOES", "TWO SECONDS IN 🥹",
    "THE QUIET ONES HIT", "GENTLE GIANT", "TINY AND FEARLESS", "THIS JUST HAPPENED",
    "NOT A SINGLE PLAN", "SHE RUNS THIS HOUSE", "HE THINKS HE'S BIG", "GOING SO BADLY 😭",
    "ATTEMPT FORTY-ONE", "VERY PROUD OF HIMSELF", "NO SUPERVISION HERE", "BAD PLAN, GREAT RESULT",
    "SOMEONE'S ABOUT TO LOSE", "WATCH HIM THINK", "FULL COMMITMENT", "ZERO COORDINATION",
    "THE LOOK AT THE END", "ONE MINUTE OLD FRIENDS", "HOME AT LAST ❤️", "FIRST SOFT BED",
    "FIRST TIME OUTSIDE", "HE FINALLY RELAXED", "SHE LET HIM CLOSE", "TOOK A MONTH 🥹",
    "LAST ONE LEFT", "SOMEBODY PICKED HIM", "THIS IS TRUST", "NO WORDS NEEDED",
    "SHE ALWAYS WAITS", "HE CHECKS ON HER", "EVERY SINGLE MORNING", "THE SAME SPOT DAILY",
    "SHE NEVER MISSES", "STILL WAITING 🥺", "GUARDING HIS BABY", "THE GENTLEST BOY",
    "SHE PICKED THE BABY", "TOO SMALL TO KNOW", "MADE MY WHOLE WEEK", "FOR A HARD DAY",
    "TAKE THIRTY SECONDS", "THIS IS THE GOOD PART", "SOMETHING SOFT TODAY", "STAY A SECOND",
]

# ==========================================================================
# FLASH PHRASES  (72)
# ==========================================================================
# NEW. Shown 3 times mid-video for a little over a second each, in the upper
# third with no backdrop panel.
#
# This exists because rolling word-by-word captions were switched off on purpose
# (they looked cluttered over the footage), which left a muted viewer with no
# text at all after the opening hook. A few short flashes keep something to read
# without covering the animal or the baby, which is the whole point of the shot.
FLASH_PHRASES = [
    "WAIT...", "HERE IT COMES", "WATCH THIS", "THERE IT IS", "LOOK 👀",
    "AND THEN 🥹", "THE BEST BIT", "OH NO 😭", "TOO CUTE", "AWWW",
    "HE DID IT", "SHE DID IT", "THAT FACE", "THOSE EYES", "THAT LITTLE SIGH",
    "ALMOST 🥺", "ANY SECOND NOW", "KEEP GOING", "ONE MORE TRY", "HE'S TRYING",
    "SO CLOSE", "NAILED IT", "PROUD BOY", "TINY LEGS", "FULL SPEED",
    "NO BRAKES", "STRAIGHT IN", "COMMITTED", "ZERO FEAR", "BRAVE LITTLE THING",
    "THE TAIL 🥹", "THE EARS", "THE PAWS", "LOOK AT HIM GO", "PURE JOY",
    "BEST FRIENDS", "TOGETHER NOW", "SHE WAITED", "HE CAME BACK", "RIGHT ON TIME",
    "EVERY DAY THIS", "SAME SPOT", "STILL THERE", "NEVER LEAVES", "ALWAYS GENTLE",
    "SO CAREFUL", "SO SOFT", "SLOWLY NOW", "TRUST 🤍", "SAFE AT LAST",
    "FIRST TIME", "BRAND NEW", "NEVER SEEN THIS", "WHAT IS THAT", "NEW FAVOURITE",
    "MINE NOW", "NO SHARING", "SHE DECIDED", "HE HAS OPINIONS", "NOT MOVING",
    "GOOD LUCK 😅", "IT'S HAPPENING", "HERE WE GO", "PLOT TWIST", "DIDN'T SEE IT",
    "OKAY THEN", "WELL THEN 😭", "MY HEART", "I'M DONE 🥹", "THIS ONE HURTS",
    "WATCH TO THE END", "ALMOST OVER, STAY",
    # Three flashes are used per reel, so this pool drains three times faster
    # than the others. Extended so it lasts roughly ten days at 5 reels/day.
    "HOLD ON 🥹", "NEARLY THERE", "ONE SECOND MORE", "RIGHT HERE", "THIS BIT 👇",
    "LISTEN 🔊", "DID YOU SEE", "AGAIN? OKAY", "ONE MORE TIME", "STILL GOING",
    "NO STOPPING HIM", "SHE'S HAD ENOUGH", "HE'S SO PLEASED", "TAIL GOING WILD",
    "EARS UP 🥺", "TINY YAWN", "SLEEPY BOY", "OUT COLD", "FAST ASLEEP",
    "SNORING NOW", "WARM AND SAFE", "TUCKED IN", "HIS OWN BED", "NEW BLANKET",
    "FIRST NAP HERE", "FEELS SAFE NOW", "NO MORE HIDING", "CAME OUT AT LAST",
    "TOOK HER TIME", "WORTH THE WAIT", "FINALLY 🥹", "THERE SHE IS",
    "HE REMEMBERED", "STILL KNOWS HER", "NEVER FORGOT", "SAME LOVE",
    "EVERY EVENING", "LIKE CLOCKWORK", "HER SPOT", "HIS JOB NOW",
    "ON DUTY", "GUARD MODE", "NOBODY MOVES", "VERY SERIOUS BUSINESS",
    "FULL CONCENTRATION", "MASSIVE EFFORT", "SO MUCH TRYING", "ALMOST GOT IT",
    "OH DEAR 😅", "NOT LIKE THAT", "TRY AGAIN BUDDY", "CLOSE ENOUGH",
    "GOOD ENOUGH FOR HIM", "PROBLEM SOLVED", "HIS OWN WAY", "IT WORKED?!",
    "SOMEHOW YES", "WE DON'T KNOW EITHER", "PHYSICS WHO", "MAKES NO SENSE",
    "PERFECTLY BALANCED", "ZERO REGRETS", "TOTALLY WORTH IT", "NO NOTES",
    "SHE APPROVES", "HE APPROVES", "APPROVED ✅", "CERTIFIED CUTE",
    "TOO PURE", "SO TINY", "SO SMALL", "LOOK HOW LITTLE",
    "BIG WORLD, SMALL PUP", "BRAVE TODAY", "PROUD OF HIM", "PROUD OF HER",
    "WE LOVE HIM", "WE LOVE HER", "PROTECT THEM BOTH", "THAT'S THE ONE",
]

# ==========================================================================
# SIGN-OFFS  (20)
# ==========================================================================
# The narrator's closing line. A single fixed sign-off across a whole library is
# both a mass-production tell and a cue that trains regulars to swipe early.
CTA_CANDIDATES = [
    "Follow SweetSoul Stories for your daily dose of joy.",
    "Subscribe to SweetSoul Stories — a new little moment like this every day.",
    "There's a new sweet story here every single day. Come back tomorrow.",
    "If this made you smile, SweetSoul Stories has one of these for you daily.",
    "Stay for tomorrow's story. It's just as soft as this one.",
    "Subscribe and let something gentle find you every day.",
    "SweetSoul Stories, every day, for the days you need something kind.",
    "Follow along — the next tiny story is already waiting.",
    "One small, sweet story every day. Subscribe and we'll see you tomorrow.",
    "If your day got a little better, that's all we wanted. Subscribe for more.",
    "Come back tomorrow. There's always another small moment worth seeing.",
    "Subscribe, and let us hand you one good thing every single day.",
    "That's today's dose of soft. Follow for tomorrow's.",
    "New story, same warmth, every day. Subscribe so you don't miss it.",
    "Follow SweetSoul Stories — tiny stories, big hearts, daily.",
    "There is more where this came from. Subscribe and find out.",
    "Stay a while. We post something gentle here every day.",
    "Subscribe for more of the quiet, lovely parts of the internet.",
    "Tomorrow's story is already waiting for you. Follow along.",
    "If you needed this today, subscribe — we'll be here again tomorrow.",
    # The sign-off is the last thing a viewer hears on every single reel, so a
    # small pool is more noticeable here than anywhere else. Extended so it
    # cycles roughly every nine days rather than every four.
    "Subscribe for one small, kind story a day. That's all we do here.",
    "Follow for more of this. Tomorrow's is already written.",
    "If that helped even a little, subscribe and we'll do it again tomorrow.",
    "Every day, one gentle story. Subscribe and let it find you.",
    "Stick around. The next one is just as soft as this.",
    "Subscribe to SweetSoul Stories and let the good part reach you daily.",
    "That's all for today. Follow along and we'll see you tomorrow.",
    "Come for one story, stay for the daily ones. Subscribe.",
    "Follow SweetSoul Stories — we keep the gentle ones coming.",
    "Subscribe, and tomorrow this will find you again.",
    "One tiny story a day, every day. Subscribe so you catch the next.",
    "If this was your favourite thirty seconds today, subscribe for tomorrow's.",
    "Follow for daily reminders that small things carry a lot of love.",
    "Subscribe — there's a new little moment here every single morning.",
    "We'll be back tomorrow with another one. Follow so you don't miss it.",
    "Save this channel for the days you need something soft. Subscribe.",
    "Subscribe for the quiet, lovely corner of your feed.",
    "New story every day, no exceptions. Follow SweetSoul Stories.",
    "If you smiled, that's the whole job done. Subscribe for more.",
    "Follow along, and tomorrow we'll find another one of these together.",
    "Subscribe — the next small, sweet thing is one day away.",
    "One good thing a day. Subscribe and let us handle it.",
    "Stay with SweetSoul Stories. There's always another gentle one coming.",
    "Follow now, and tomorrow's story will be waiting for you.",
    "Subscribe for daily proof that the world still has soft edges.",
]

# ==========================================================================
# FOOTAGE KEYWORDS (fallback)
# ==========================================================================
# Used when Gemini returns no keywords of its own. Deliberately breed-free: the
# footage is random stock, so naming a breed guarantees a mismatch.
DEFAULT_KEYWORDS = [
    "puppy playing in grass sunlight",
    "puppy sleeping on blanket",
    "baby laughing outdoor",
    "kitten playing near window light",
    "toddler playing with puppy outside",
    "dog and baby in garden",
    "fluffy puppy running outdoor",
    "baby and puppy sunny day",
    "kittens playing in sunlight",
    "child hugging dog outdoor",
    "cat cuddling with child",
    "baby crawling toward dog",
    "toddler feeding kitten",
    "dog wagging tail happy",
    "kitten yawning close up",
    "children playing with pets backyard",
]


# ==========================================================================
# Self-check
# ==========================================================================
# Duplicates inside a pool silently shrink it and defeat the no-repeat history,
# so they are worth catching immediately rather than in a month's output.
POOLS = {
    "topics": TOPIC_POOL,
    "hooks": HOOK_CANDIDATES,
    "screen_hooks": SCREEN_HOOKS,
    "flashes": FLASH_PHRASES,
    "ctas": CTA_CANDIDATES,
    "keywords": DEFAULT_KEYWORDS,
}


def audit():
    """Return {pool_name: (size, [duplicates])} for every pool."""
    report = {}
    for name, pool in POOLS.items():
        seen, dupes = set(), []
        for item in pool:
            key = item.strip().lower()
            if key in seen:
                dupes.append(item)
            seen.add(key)
        report[name] = (len(pool), dupes)
    return report


if __name__ == "__main__":
    problems = 0
    for name, (size, dupes) in sorted(audit().items()):
        flag = "OK" if not dupes else f"{len(dupes)} DUPLICATE(S)"
        print(f"{name:<14}{size:>5} items   {flag}")
        for d in dupes:
            print(f"                    - {d}")
        problems += len(dupes)
    raise SystemExit(1 if problems else 0)
