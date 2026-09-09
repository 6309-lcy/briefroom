"""Case pack = one full LLM call. Assessor = input-budgeted pipeline."""

from __future__ import annotations

import logging
from typing import Any

from ..llm import complete_json, estimate_tokens, input_budget
from ..prompts import (
    ASSESSOR_EVIDENCE_SYSTEM,
    ASSESSOR_SCORES_SYSTEM,
    ASSESSOR_SYSTEM,
    ASSESSOR_WRAP_SYSTEM,
    CASE_SYSTEM,
    assessor_evidence_user,
    assessor_scores_user,
    assessor_user,
    assessor_wrap_user,
    case_user,
)

log = logging.getLogger("briefroom.compose")

CONTENT_SCORES = [
    ("structure", "Structure"),
    ("commercial", "Commercial judgement"),
    ("insight", "Insight from materials"),
]
PEOPLE_SCORES = [
    ("influence", "Influence & presence"),
    ("teamwork", "Teamwork"),
    ("composure", "Composure under pressure"),
]

CASE_OUTPUT_TOKENS = 7000
EVIDENCE_OUTPUT_TOKENS = 2200
SCORE_OUTPUT_TOKENS = 2000
WRAP_OUTPUT_TOKENS = 2200


def _dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return raw[0]
    return {}


async def _json(system: str, user: str, *, temperature: float, max_tokens: int) -> dict:
    try:
        data = await complete_json(
            system,
            user,
            strong=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _dict(data)
    except Exception:
        log.exception("compose step failed")
        return {}


async def compose_case(industry: dict, difficulty: str, extra: str) -> dict:
    """Single call so brief, exhibits, and rubric stay one coherent pack."""
    log.info("case generation: one-shot max_tokens=%s", CASE_OUTPUT_TOKENS)
    payload = await _json(
        CASE_SYSTEM,
        case_user(industry, difficulty, extra),
        temperature=0.7,
        max_tokens=CASE_OUTPUT_TOKENS,
    )
    payload.setdefault("industry_label", industry.get("name"))
    payload.setdefault("exhibits", [])
    payload.setdefault(
        "hidden_rubric",
        {"what_good_looks_like": [], "common_traps": [], "must_hit_points": []},
    )
    payload.setdefault("constraints", [])
    return payload


def _clip(text: str, chars: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= chars:
        return raw
    return raw[: chars - 1] + "…"


def _format_turn(turn: dict, width: int) -> str:
    flag = " [INTERRUPT]" if turn.get("interrupt") else ""
    phase = turn.get("phase") or ""
    return f"{turn.get('speaker_name')}:{flag} ({phase}) {_clip(turn.get('text') or '', width)}"


def pack_transcript(turns: list[dict], budget_tokens: int) -> str:
    """Fit 3 AI scripts + the candidate into the model input window.

    Keep every candidate line first. Fill the rest with other-speaker
    lines (interrupts, then recency) until the token budget is spent.
    """
    if budget_tokens < 200:
        budget_tokens = 200
    user = [t for t in turns if t.get("speaker_id") == "user"]
    others = [t for t in turns if t.get("speaker_id") != "user"]

    user_width = 360
    user_block: list[str] = []
    while True:
        user_block = [_format_turn(t, user_width) for t in user]
        header_used = estimate_tokens(
            "\n".join(["# Candidate lines"] + (user_block or ["(none)"]) + ["# Other speakers"])
        )
        if header_used <= budget_tokens * 7 // 10 or user_width <= 80 or not user:
            break
        user_width = max(80, user_width - 80)

    def render(kept_rows: list[tuple[int, dict]]) -> str:
        dropped = len(others) - len(kept_rows)
        other_lines = [_format_turn(t, 220 if t.get("interrupt") else 140) for _, t in kept_rows]
        parts = (
            ["# Candidate lines"]
            + (user_block or ["(The candidate barely spoke.)"])
            + [f"# Other speakers ({len(kept_rows)} of {len(others)} turns; {dropped} dropped to fit context)"]
            + (other_lines or ["(other candidates truncated to fit the model context window)"])
        )
        return "\n".join(parts)

    kept: list[tuple[int, dict]] = []
    ranked = sorted(
        enumerate(others),
        key=lambda it: (0 if it[1].get("interrupt") else 1, -it[0]),
    )
    for idx, turn in ranked:
        trial = kept + [(idx, turn)]
        trial.sort(key=lambda it: it[0])
        if estimate_tokens(render(trial)) <= budget_tokens:
            kept = trial

    packed = render(kept)
    while estimate_tokens(packed) > budget_tokens and user_block:
        user_block = [_clip(line, max(48, len(line) * 3 // 4)) for line in user_block]
        packed = render(kept)
        if all(len(line) <= 56 for line in user_block):
            packed = packed[: max(200, budget_tokens * 4 - 1)]
            break
    log.info(
        "packed transcript ~%s tokens (budget %s); user=%s others_kept=%s/%s",
        estimate_tokens(packed),
        budget_tokens,
        len(user),
        len(kept),
        len(others),
    )
    return packed


def _transcript_budget(output_tokens: int) -> int:
    """Leave room for system + case header inside the strong-model input window."""
    total = input_budget(output_tokens, strong=True)
    # Case header / rubric is small; keep most of the budget for the floor.
    return max(800, total - 700)


async def compose_debrief(case: dict, transcript: list[dict], user_name: str) -> dict:
    """Never send the raw 3-bot + user log in one shot.

    1. Pack the transcript to the tightest model context in the fallback chain.
    2. Evidence from that pack.
    3. Score two competency groups from evidence only.
    4. Wrap headline / verdict / summary from scores + evidence.
    """
    packed = pack_transcript(transcript, _transcript_budget(EVIDENCE_OUTPUT_TOKENS))

    log.info("debrief pipeline: evidence")
    evidence = await _json(
        ASSESSOR_EVIDENCE_SYSTEM,
        assessor_evidence_user(case, packed, user_name),
        temperature=0.3,
        max_tokens=EVIDENCE_OUTPUT_TOKENS,
    )
    if not evidence:
        evidence = {"speaking_pattern": "thin record", "quotes": [], "misses": ["barely evidenced"]}

    log.info("debrief pipeline: content scores")
    content = await _json(
        ASSESSOR_SCORES_SYSTEM,
        assessor_scores_user(case, user_name, evidence, CONTENT_SCORES),
        temperature=0.3,
        max_tokens=SCORE_OUTPUT_TOKENS,
    )
    log.info("debrief pipeline: people scores")
    people = await _json(
        ASSESSOR_SCORES_SYSTEM,
        assessor_scores_user(case, user_name, evidence, PEOPLE_SCORES),
        temperature=0.3,
        max_tokens=SCORE_OUTPUT_TOKENS,
    )
    competencies = _merge_competencies(content.get("competencies"), people.get("competencies"), evidence)

    log.info("debrief pipeline: wrap")
    wrap = await _json(
        ASSESSOR_WRAP_SYSTEM,
        assessor_wrap_user(case, user_name, evidence, competencies),
        temperature=0.35,
        max_tokens=WRAP_OUTPUT_TOKENS,
    )
    if not wrap.get("headline"):
        wrap = await _json(
            ASSESSOR_SYSTEM,
            assessor_user(case, transcript, user_name),
            temperature=0.35,
            max_tokens=WRAP_OUTPUT_TOKENS,
        )
        if wrap.get("competencies"):
            return wrap

    scores = [float(c.get("score") or 0) for c in competencies]
    overall = wrap.get("overall")
    try:
        overall = float(overall)
    except (TypeError, ValueError):
        overall = round(sum(scores) / max(len(scores), 1), 1)
    overall = max(1.0, min(5.0, overall))
    moments = wrap.get("moments") or [
        {"quote": q.get("text"), "comment": q.get("why_it_matters") or "From the floor.", "turn_id": None}
        for q in (evidence.get("quotes") or [])[:3]
        if isinstance(q, dict)
    ]
    return {
        "headline": wrap.get("headline") or "Marked from the transcript",
        "overall": overall,
        "verdict": wrap.get("verdict") or _verdict(overall),
        "competencies": competencies,
        "what_worked": list(wrap.get("what_worked") or [])[:4],
        "what_to_change": list(wrap.get("what_to_change") or [])[:4],
        "moments": moments[:4],
        "summary": wrap.get("summary") or evidence.get("speaking_pattern") or "",
    }


def _merge_competencies(a: Any, b: Any, evidence: dict) -> list[dict]:
    found = {}
    for row in list(a or []) + list(b or []):
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "")
        if cid:
            found[cid] = row
    out = []
    for cid, label in CONTENT_SCORES + PEOPLE_SCORES:
        row = found.get(cid) or {}
        try:
            score = int(round(float(row.get("score") or 3)))
        except (TypeError, ValueError):
            score = 3
        score = max(1, min(5, score))
        note = (row.get("note") or evidence.get("speaking_pattern") or "Thin evidence in the transcript.").strip()
        out.append({"id": cid, "label": row.get("label") or label, "score": score, "note": note})
    return out


def _verdict(overall: float) -> str:
    if overall >= 4.3:
        return "strong hire"
    if overall >= 3.5:
        return "hire"
    if overall >= 2.7:
        return "borderline"
    return "no hire"
