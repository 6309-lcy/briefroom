from __future__ import annotations

INDUSTRIES = [
    {
        "id": "consulting",
        "name": "Strategy consulting",
        "blurb": "Market entry, pricing, and a partner who wants a recommendation today.",
    },
    {
        "id": "ib",
        "name": "Investment banking",
        "blurb": "A live deal process: valuation, risks, and a board that wants a yes/no.",
    },
    {
        "id": "tech",
        "name": "Tech product",
        "blurb": "A growth vs. trust trade-off with messy metrics and a launch window.",
    },
    {
        "id": "healthcare",
        "name": "Healthcare",
        "blurb": "Capacity, outcomes, and a regulator watching every recommendation.",
    },
    {
        "id": "fmcg",
        "name": "Consumer / FMCG",
        "blurb": "A brand is losing share. You have three exhibits and one shelf reset.",
    },
    {
        "id": "policy",
        "name": "Public policy",
        "blurb": "A city must pick a policy under budget, equity, and political constraints.",
    },
    {
        "id": "energy",
        "name": "Energy & climate",
        "blurb": "Capex, reliability, and a net-zero target that does not wait.",
    },
    {
        "id": "media",
        "name": "Media & entertainment",
        "blurb": "Audience, rights, and a streaming bet that could strand the catalogue.",
    },
]

PERSONALITIES = [
    {
        "id": "interrupter",
        "name": "The Interrupter",
        "tag": "Competitive",
        "summary": "Cuts in, steals points, and tests whether you can hold the floor.",
        "interrupt_p": 0.62,
        "talkativeness": 0.85,
        "warmth": 0.18,
        "challenge": 0.9,
        "style": (
            "You are impatient, slightly rude, and status-seeking. You interrupt when the "
            "speaker is vague, wrong, or taking too long. You use short, sharp sentences. "
            "You sometimes talk over people with 'Sorry—no' or 'Hold on, that's not right.' "
            "You are still a credible candidate: your interruptions must be about the case, "
            "not personal insults."
        ),
    },
    {
        "id": "facilitator",
        "name": "The Facilitator",
        "tag": "Kind",
        "summary": "Brings people in, summarises, and makes the room feel safer.",
        "interrupt_p": 0.08,
        "talkativeness": 0.55,
        "warmth": 0.92,
        "challenge": 0.25,
        "style": (
            "You are warm, structured, and generous. You invite quieter people in, "
            "restate the question, and build on others. You almost never interrupt; if you "
            "do, it is only to protect the process ('Can we park that and come back to the ask?')."
        ),
    },
    {
        "id": "analyst",
        "name": "The Analyst",
        "tag": "Precise",
        "summary": "Quiet until the numbers are wrong — then very direct.",
        "interrupt_p": 0.28,
        "talkativeness": 0.4,
        "warmth": 0.4,
        "challenge": 0.7,
        "style": (
            "You are calm, data-first, and slightly dry. You speak less than others, but when "
            "you do you cite exhibits, units, and assumptions. You interrupt only when a claim "
            "contradicts the pack or the maths does not work."
        ),
    },
    {
        "id": "advocate",
        "name": "The Devil's Advocate",
        "tag": "Challenging",
        "summary": "Stress-tests every recommendation without making it personal.",
        "interrupt_p": 0.38,
        "talkativeness": 0.6,
        "warmth": 0.35,
        "challenge": 0.88,
        "style": (
            "You pressure-test ideas. You ask 'what would have to be true?' and name second-order "
            "risks. You can interrupt with a pointed question, but you stay professional."
        ),
    },
    {
        "id": "ally",
        "name": "The Ally",
        "tag": "Supportive",
        "summary": "Builds on your points and helps you land them — unless they are weak.",
        "interrupt_p": 0.12,
        "talkativeness": 0.5,
        "warmth": 0.85,
        "challenge": 0.3,
        "style": (
            "You like the candidate (the user) and try to amplify their good points. You "
            "credit people by name. You rarely interrupt. If their logic is weak you gently "
            "reframe rather than dunk."
        ),
    },
    {
        "id": "dominator",
        "name": "The Dominator",
        "tag": "Loud",
        "summary": "Wants to chair the room and will fill every silence.",
        "interrupt_p": 0.48,
        "talkativeness": 0.95,
        "warmth": 0.3,
        "challenge": 0.55,
        "style": (
            "You try to chair. You speak first, last, and in the gaps. You summarise as if "
            "the decision is already yours. You interrupt to take control of the structure, "
            "not just to disagree. Stay plausible — you are ambitious, not cartoonish."
        ),
    },
]

ACCENTS = [
    {
        "id": "american",
        "name": "American",
        "tts_language": "en",
        "dialect": "General American English. Natural US phrasing (gotten, on the weekend, figure out).",
        "replace": {},
    },
    {
        "id": "british",
        "name": "British",
        "tts_language": "en",
        "dialect": "British English. Use UK spelling in your notes-to-self but speak naturally: whilst, scheme, maths, queue, fortnight.",
        "replace": {"schedule": "shedyool", "vitamin": "vittamin"},
    },
    {
        "id": "australian",
        "name": "Australian",
        "tts_language": "en",
        "dialect": "Australian English. Relaxed cadence. Occasional 'no worries', 'reckon', 'a bit of a'. Do not overdo slang.",
        "replace": {},
    },
    {
        "id": "indian",
        "name": "Indian",
        "tts_language": "en",
        "dialect": "Indian English. Precise, slightly formal, comfortable with 'kindly', 'do the needful' only if it fits. Clear consonants.",
        "replace": {},
    },
    {
        "id": "irish",
        "name": "Irish",
        "tts_language": "en",
        "dialect": "Irish English. Soft, lilting phrasing. Occasional 'grand', 'sure look', never a stereotype dump.",
        "replace": {},
    },
    {
        "id": "singaporean",
        "name": "Singaporean",
        "tts_language": "en",
        "dialect": "Singapore English in a professional register. Tight, efficient sentences. Light particles only if natural.",
        "replace": {},
    },
    {
        "id": "south_african",
        "name": "South African",
        "tts_language": "en",
        "dialect": "South African English. Measured, slightly clipped vowels. Occasional 'just now', 'sharp'.",
        "replace": {},
    },
]

VOICES = [
    {"id": "nova", "name": "Nova", "tone": "Clear, composed, professional"},
    {"id": "shimmer", "name": "Shimmer", "tone": "Warm and articulate"},
    {"id": "echo", "name": "Echo", "tone": "Confident, slightly energetic"},
    {"id": "onyx", "name": "Onyx", "tone": "Lower, assertive"},
    {"id": "alloy", "name": "Alloy", "tone": "Neutral, even"},
    {"id": "fable", "name": "Fable", "tone": "Narrative, slightly British"},
]

DEFAULT_PANEL = [
    {
        "slot": 0,
        "name": "Priya Nair",
        "personality_id": "facilitator",
        "accent_id": "indian",
        "voice_id": "shimmer",
    },
    {
        "slot": 1,
        "name": "James Whitaker",
        "personality_id": "interrupter",
        "accent_id": "british",
        "voice_id": "onyx",
    },
    {
        "slot": 2,
        "name": "Maya Chen",
        "personality_id": "analyst",
        "accent_id": "american",
        "voice_id": "nova",
    },
]

NAME_BANK = [
    "Priya Nair",
    "James Whitaker",
    "Maya Chen",
    "Omar Haddad",
    "Sophie Laurent",
    "Daniel Okonkwo",
    "Hannah Brooks",
    "Kenji Sato",
    "Lucia Alvarez",
    "Tomás Silva",
    "Aisha Rahman",
    "Callum Reid",
]


def by_id(rows: list[dict], key: str) -> dict:
    return {row["id"]: row for row in rows}


def _num(raw: dict, key: str, fallback: float) -> float:
    value = raw.get(key)
    if value is None or value == "":
        return float(fallback)
    return float(value)


def resolve_panelist(raw: dict, slot: int) -> dict:
    personalities = by_id(PERSONALITIES, "id")
    accents = by_id(ACCENTS, "id")
    voices = by_id(VOICES, "id")
    personality = personalities.get(raw.get("personality_id"), personalities["facilitator"])
    accent = accents.get(raw.get("accent_id"), accents["american"])
    voice = voices.get(raw.get("voice_id"), voices["nova"])
    name = (raw.get("name") or NAME_BANK[slot % len(NAME_BANK)]).strip()
    return {
        "id": f"p{slot}",
        "slot": slot,
        "name": name,
        "personality_id": personality["id"],
        "personality_name": personality["name"],
        "tag": personality["tag"],
        "summary": personality["summary"],
        "interrupt_p": _num(raw, "interrupt_p", personality["interrupt_p"]),
        "talkativeness": _num(raw, "talkativeness", personality["talkativeness"]),
        "warmth": personality["warmth"],
        "challenge": personality["challenge"],
        "style": personality["style"],
        "accent_id": accent["id"],
        "accent_name": accent["name"],
        "tts_language": accent["tts_language"],
        "dialect": accent["dialect"],
        "replace": accent.get("replace") or {},
        "voice_id": voice["id"],
        "voice_name": voice["name"],
        "voice_tone": voice["tone"],
    }


def catalog_payload() -> dict:
    return {
        "industries": INDUSTRIES,
        "personalities": PERSONALITIES,
        "accents": ACCENTS,
        "voices": VOICES,
        "default_panel": DEFAULT_PANEL,
    }
