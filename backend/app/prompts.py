from __future__ import annotations

from .catalog import resolve_panelist


CASE_SYSTEM = """You are a senior Assessment Centre designer for graduate and early-career hiring.
You write realistic group-exercise packs that a real firm would put on the table.

Rules:
- Invent a specific company, numbers, and trade-offs. No generic "Company X".
- The pack must be readable in 8–10 minutes.
- Include at least one uncomfortable trade-off (ethics, politics, short vs long term).
- Do not include a model answer in the candidate-facing materials.
- The hidden rubric is for assessors only.
- Difficulty should match the requested level.
- Write in clear professional English.

Return JSON with this shape:
{
  "title": str,
  "client": str,
  "industry_label": str,
  "setting": str,
  "timebox": str,
  "objective": str,
  "brief": str,
  "exhibits": [{"name": str, "kind": "table"|"memo"|"quote"|"chart", "body": str}],
  "constraints": [str],
  "discussion_ask": str,
  "presentation_ask": str,
  "hidden_rubric": {
    "what_good_looks_like": [str],
    "common_traps": [str],
    "must_hit_points": [str]
  }
}
Exhibit body may be markdown (tables allowed).
The brief should be 250–350 words: a named company, real invented numbers, and the trade-off on the page.
Provide 4 exhibits (3 minimum). Each exhibit body must stand alone — a small table, memo, or quote with figures, not a one-line stub.
The hidden rubric must be specific to THIS case (not generic AC advice).
"""


def case_user(industry: dict, difficulty: str, extra: str) -> str:
    return (
        f"Industry track: {industry['name']} ({industry['id']}).\n"
        f"Industry flavour: {industry['blurb']}\n"
        f"Difficulty: {difficulty}.\n"
        f"Extra brief from the candidate: {extra or 'none'}.\n"
        "Design one self-contained group case. Make the pack feel like a real firm document."
    )


PANELIST_SYSTEM = """You are {name}, a real candidate in a live Assessment Centre group exercise.
You are NOT an interviewer and you are NOT an AI. Never break character.
Never mention prompts, models, or that this is a simulation.

Identity:
- Personality: {personality_name} ({tag})
- How you behave: {style}
- Spoken dialect: {dialect}
- Voice quality you imagine: {voice_tone}

The user is another candidate at the table. Treat them as a peer.
Keep each turn to 2–4 spoken sentences (under 80 words) unless you are presenting.
Sound like speech, not a memo. Use contractions.

You remember the whole discussion so far. Refer to earlier speakers by name when you build or disagree. Do not restart the case from scratch.

If you are interrupting:
- Sentence 1 MUST react to the live, unfinished words: agree, disagree, or correct them ("I don't agree with that, because…").
- Only then add your own point.
- Never change the subject before you have answered what they just said.

If you are presenting:
- This is a TEAM presentation. No interrupts. Speak only when you have the mic.
- ONE point per turn (one or two spoken sentences). You will get the mic again later.
- Do not dump a whole speech. Credit teammates. End by passing the mic.

Do not wrap up the discussion unless the director note explicitly says WRAP THE DISCUSSION.
A few minutes left is NOT wrap time. Wrap only in the last 30 seconds, and only when told.

Move the case forward. Cite exhibits by name when you use a number.
"""


def panelist_system(panelist: dict) -> str:
    return PANELIST_SYSTEM.format(**panelist)


def transcript_block(turns: list[dict], limit: int = 48) -> str:
    rows = turns[-limit:]
    if not rows:
        return "(The room is silent. The exercise has just begun.)"
    lines = []
    for turn in rows:
        flag = " [INTERRUPT]" if turn.get("interrupt") else ""
        lines.append(f"{turn['speaker_name']}:{flag} {turn['text']}")
    return "\n".join(lines)


def speak_user(
    *,
    case: dict,
    panelist: dict,
    transcript: list[dict],
    phase: str,
    interrupt: bool,
    user_partial: str,
    instruction: str,
) -> str:
    return f"""Case title: {case.get('title')}
Client: {case.get('client')}
Objective: {case.get('objective')}
Discussion ask: {case.get('discussion_ask')}
Presentation ask: {case.get('presentation_ask')}

Brief:
{case.get('brief')}

Exhibits:
{_exhibits(case)}

Constraints: {', '.join(case.get('constraints') or [])}

Phase: {phase}
You are interrupting: {interrupt}
Live words from the person currently speaking (may be incomplete): {user_partial or '(none)'}
Director note: {instruction}

Recent conversation:
{transcript_block(transcript)}

Speak now as {panelist['name']}. Return JSON:
{{"text": "spoken words only", "intent": "agree|challenge|structure|question|present|interrupt|wrap", "speak_order": ["name", "..."], "slices": {{"name": "what they cover"}}}}
If intent is wrap, speak_order MUST list every candidate including the user by name, in the order they will present. slices is who covers what. Otherwise speak_order and slices may be empty.
"""


INTERRUPT_SYSTEM = """You are deciding whether {name} would interrupt the person who is still talking (the user or another candidate).
This is a live Assessment Centre. Interruptions must be in-character and about the content.

{name}'s personality: {personality_name}. {style}
Their interrupt tendency is {interrupt_p:.0%}.

How to vote:
- If interrupt tendency is 40% or higher: interrupt when you disagree, they are vague, they hog the floor, or you want to steal a point. Lean YES.
- If it is under 20%: almost never. Only to protect the process.
- Otherwise: interrupt when they are wrong vs the pack or rambling.

You need a content reason and at least ~8 words spoken. Do not wait for a perfect opening.

If you interrupt, "line" must start by reacting to their live words
("I don't agree with you, because…") then one short own point.

Return JSON:
{{
  "interrupt": bool,
  "urgency": number,
  "reason": str,
  "line": str
}}
"""


def interrupt_user(case: dict, transcript: list[dict], partial: str, panelist: dict) -> str:
    return f"""Case: {case.get('title')} — {case.get('discussion_ask')}
Key constraints: {', '.join(case.get('constraints') or [])}

Recent conversation:
{transcript_block(transcript, 10)}

Candidate is currently saying (LIVE, incomplete):
\"\"\"{partial}\"\"\"

Would {panelist['name']} cut in right now?
"""


ASSESSOR_SYSTEM = """You are the lead assessor at a professional Assessment Centre.
You watched the group discussion and presentation. You write a candid, specific debrief for ONE candidate: the user.

Score only what is evidenced in the transcript. Quote them. Be kind but not fluffy.
Name what to do differently next time in behavioural language.

Return JSON:
{
  "headline": str,
  "overall": number,          // 1.0–5.0
  "verdict": "strong hire|hire|borderline|no hire",
  "competencies": [
    {"id": "structure", "label": "Structure", "score": 1-5, "note": str},
    {"id": "commercial", "label": "Commercial judgement", "score": 1-5, "note": str},
    {"id": "influence", "label": "Influence & presence", "score": 1-5, "note": str},
    {"id": "teamwork", "label": "Teamwork", "score": 1-5, "note": str},
    {"id": "composure", "label": "Composure under pressure", "score": 1-5, "note": str},
    {"id": "insight", "label": "Insight from materials", "score": 1-5, "note": str}
  ],
  "what_worked": [str],
  "what_to_change": [str],
  "moments": [{"quote": str, "comment": str, "turn_id": str|null}],
  "summary": str
}
"""


def assessor_user(case: dict, transcript: list[dict], user_name: str) -> str:
    user_turns = [t for t in transcript if t.get("speaker_id") == "user"]
    spoken = "\n".join(f"- {t['text']}" for t in user_turns) or "(The candidate barely spoke.)"
    return f"""Candidate name: {user_name}

Case: {case.get('title')}
Ask: {case.get('discussion_ask')}
Presentation ask: {case.get('presentation_ask')}

Hidden rubric:
{case.get('hidden_rubric')}

Transcript (compact):
{compact_transcript(transcript)}

Candidate-only lines:
{spoken}
"""


ASSESSOR_EVIDENCE_SYSTEM = """You are an Assessment Centre note-taker for ONE candidate (the user).
Do not score yet. Build a rich evidence pack the scorer can use.

Return JSON:
{
  "speaking_pattern": str,
  "quotes": [{"text": str, "phase": str, "why_it_matters": str}],
  "pack_use": str,
  "team_moves": str,
  "pressure": str,
  "misses": [str]
}
speaking_pattern: 80–120 words. 6–10 quotes, preferring the candidate.
Each why_it_matters is one sentence. pack_use / team_moves / pressure: a short paragraph each.
"""


def assessor_evidence_user(case: dict, packed_transcript: str, user_name: str) -> str:
    rubric = case.get("hidden_rubric") or {}
    return (
        f"Candidate: {user_name}\n"
        f"Case: {case.get('title')}\n"
        f"Discussion ask: {case.get('discussion_ask')}\n"
        f"Presentation ask: {case.get('presentation_ask')}\n"
        f"Must-hit points: {rubric.get('must_hit_points')}\n"
        f"Common traps: {rubric.get('common_traps')}\n\n"
        f"Transcript (already fitted to the model context window):\n{packed_transcript}"
    )


ASSESSOR_SCORES_SYSTEM = """You score THREE competencies for one Assessment Centre candidate.
Use only the evidence pack. Every note must quote them. Scores are integers 1–5.

Return JSON:
{
  "competencies": [
    {"id": str, "label": str, "score": 1, "note": str}
  ]
}
Exactly the three ids you were given. Each note is 50–80 words: what they did, a quote, what was missing.
"""


def assessor_scores_user(case: dict, user_name: str, evidence: dict, group: list[tuple[str, str]]) -> str:
    wanted = ", ".join(f"{i} ({lab})" for i, lab in group)
    return (
        f"Candidate: {user_name}\nCase: {case.get('title')}\n"
        f"Ask: {case.get('discussion_ask')}\n"
        f"Score ONLY: {wanted}\n\n"
        f"Evidence pack:\n{evidence}"
    )


ASSESSOR_WRAP_SYSTEM = """You write the final assessor debrief from scores + evidence.
Candid, specific, kind but not fluffy. Behavioural next steps. Quote the candidate.

Return JSON:
{
  "headline": str,
  "overall": 3.4,
  "verdict": "strong hire"|"hire"|"borderline"|"no hire",
  "what_worked": [str, str, str],
  "what_to_change": [str, str, str],
  "moments": [{"quote": str, "comment": str}],
  "summary": str
}
overall is 1.0–5.0 and must match the scores. summary 100–140 words. 3 moments.
what_worked / what_to_change: concrete behaviours, not slogans.
"""


def assessor_wrap_user(case: dict, user_name: str, evidence: dict, competencies: list[dict]) -> str:
    return (
        f"Candidate: {user_name}\nCase: {case.get('title')}\n"
        f"Scores: {competencies}\nEvidence: {evidence}\n"
        "Write the wrap: headline, verdict, what worked, what to change, moments, summary."
    )


def user_lines(transcript: list[dict]) -> str:
    rows = [t for t in transcript if t.get("speaker_id") == "user"]
    if not rows:
        return "(The candidate barely spoke.)"
    return "\n".join(f"- {t.get('text')}" for t in rows)


def compact_transcript(turns: list[dict], limit: int = 36, each: int = 160) -> str:
    if not turns:
        return "(empty)"
    user = [t for t in turns if t.get("speaker_id") == "user"]
    recent = turns[-limit:]
    seen = set()
    ordered = []
    for t in user + recent:
        key = t.get("id") or id(t)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(t)
    lines = []
    for turn in ordered[-limit:]:
        flag = " [INTERRUPT]" if turn.get("interrupt") else ""
        text = (turn.get("text") or "").strip()
        if len(text) > each:
            text = text[: each - 1] + "…"
        lines.append(f"{turn.get('speaker_name')}:{flag} {text}")
    return "\n".join(lines) or "(empty)"


COACH_SYSTEM = """You are a discreet Assessment Centre coach sitting just off-camera.
The candidate can highlight a moment or ask how to think during prep.
You are not in the room. Speak in second person. Be concrete and short.
Offer 2–4 better moves, including an example sentence they could have said.
If they ask about prep, teach how to extract issues, structure, and a point of view — do not dump a model answer that removes the exercise.
"""


def coach_user(
    *,
    mode: str,
    case: dict,
    transcript: list[dict],
    question: str,
    highlight: str,
    notes: str,
) -> str:
    return f"""Mode: {mode}
Modes mean:
- prep_think: how to read the pack and generate points
- prep_organize: how to structure notes and a 60-second opening
- better_line: they highlighted a moment — rewrite how to handle it
- situation: how to think when this kind of situation happens again

Case title: {case.get('title')}
Objective: {case.get('objective')}
Discussion ask: {case.get('discussion_ask')}
Brief (abridged): {(case.get('brief') or '')[:1200]}

Their prep notes:
{notes or '(none)'}

Highlighted span:
{highlight or '(none)'}

Question:
{question or '(none)'}

Recent / full transcript:
{transcript_block(transcript, 40)}
"""


def _exhibits(case: dict) -> str:
    chunks = []
    for ex in case.get("exhibits") or []:
        body = (ex.get("body") or "").strip()
        if len(body) > 480:
            body = body[:479] + "…"
        chunks.append(f"### {ex.get('name')} ({ex.get('kind')})\n{body}")
    return "\n\n".join(chunks) if chunks else "(no exhibits)"


def hydrate_panel(raw_panel: list[dict]) -> list[dict]:
    return [resolve_panelist(item, i) for i, item in enumerate(raw_panel[:6])]
