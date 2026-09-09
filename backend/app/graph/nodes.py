from __future__ import annotations

import random

from ..catalog import INDUSTRIES, by_id
from ..llm import complete, complete_json
from ..prompts import (
    COACH_SYSTEM,
    INTERRUPT_SYSTEM,
    coach_user,
    interrupt_user,
    panelist_system,
    speak_user,
)
from .compose import compose_case, compose_debrief
from .state import ACState


async def generate_case(state: ACState) -> dict:
    industries = by_id(INDUSTRIES, "id")
    industry = state.get("industry") or industries.get(state.get("industry_id") or "consulting")
    payload = await compose_case(
        industry,
        state.get("difficulty") or "standard",
        state.get("extra") or "",
    )
    payload.setdefault("industry_label", industry["name"])
    return {"case": payload, "industry": industry}


async def panelist_speech(state: ACState) -> dict:
    speaker_id = state.get("speaker_id")
    panelist = next(p for p in state["panelists"] if p["id"] == speaker_id)
    interrupt = bool(state.get("interrupt"))
    data = await complete_json(
        panelist_system(panelist),
        speak_user(
            case=state["case"],
            panelist=panelist,
            transcript=state.get("transcript") or [],
            phase=state.get("phase") or "discussion",
            interrupt=interrupt,
            user_partial=state.get("user_partial") or "",
            instruction=state.get("instruction")
            or ("Interrupt now." if interrupt else "Take the floor and move the discussion forward."),
        ),
        temperature=0.85,
    )
    text = (data.get("text") or "").strip()
    if not text:
        text = "Can I come in on that? I think we are answering a different question than the one in the pack."
    return {
        "speech": {
            "speaker_id": panelist["id"],
            "speaker_name": panelist["name"],
            "text": text,
            "intent": data.get("intent") or "structure",
            "interrupt": interrupt,
            "speak_order": data.get("speak_order") or [],
            "slices": data.get("slices") or {},
            "voice_id": panelist["voice_id"],
            "accent_id": panelist["accent_id"],
            "replace": panelist.get("replace") or {},
            "tts_language": panelist.get("tts_language") or "en",
        }
    }


async def interrupt_vote(state: ACState) -> dict:
    panelist = next(p for p in state["panelists"] if p["id"] == state["speaker_id"])
    partial = (state.get("user_partial") or "").strip()
    word_count = len(partial.split())
    prior = float(panelist.get("interrupt_p") or 0)
    min_words = int(state.get("min_words") or 18)
    if word_count < min_words:
        return {
            "interrupt_votes": [
                {
                    "speaker_id": panelist["id"],
                    "interrupt": False,
                    "urgency": 0,
                    "reason": "too_early",
                    "line": "",
                }
            ]
        }
    data = await complete_json(
        INTERRUPT_SYSTEM.format(**panelist),
        interrupt_user(state["case"], state.get("transcript") or [], partial, panelist),
        temperature=0.3,
    )
    phase = state.get("phase") or "discussion"
    interrupt = bool(data.get("interrupt"))
    urgency = float(data.get("urgency") or 0)
    if phase == "presentation" or state.get("wrapping_up"):
        interrupt = False
        data["reason"] = "locked stage"
    elif interrupt and urgency < 0.22:
        interrupt = False
        data["reason"] = (data.get("reason") or "") + " (urgency too low)"
    elif interrupt:
        # LLM already said yes. Personality only rarely vetoes — rude seats almost always fire.
        allow = min(0.98, 0.5 + prior * 0.8)
        if random.random() > allow:
            interrupt = False
            data["reason"] = (data.get("reason") or "") + " (held back)"
    elif prior >= 0.45 and word_count >= 10 and random.random() < prior * 0.55:
        # Competitive seats still cut in when the model is too polite.
        interrupt = True
        urgency = max(urgency, 0.55)
        data["reason"] = (data.get("reason") or "in-character cut-in") + " (personality)"
        if not (data.get("line") or "").strip():
            data["line"] = "Hold on — I don't think that's the right cut of the issue."
    return {
        "interrupt_votes": [
            {
                "speaker_id": panelist["id"],
                "speaker_name": panelist["name"],
                "interrupt": interrupt,
                "urgency": urgency,
                "reason": data.get("reason") or "",
                "line": (data.get("line") or "").strip(),
                "voice_id": panelist["voice_id"],
                "replace": panelist.get("replace") or {},
                "tts_language": panelist.get("tts_language") or "en",
            }
        ]
    }


def pick_interrupt(state: ACState) -> dict:
    votes = [v for v in (state.get("interrupt_votes") or []) if v.get("interrupt")]
    if not votes:
        return {"chosen": {}}
    votes.sort(key=lambda v: float(v.get("urgency") or 0), reverse=True)
    return {"chosen": votes[0]}


async def write_debrief(state: ACState) -> dict:
    data = await compose_debrief(
        state.get("case") or {},
        state.get("transcript") or [],
        state.get("user_name") or "Candidate",
    )
    return {"debrief": data}


async def coach_reply(state: ACState) -> dict:
    answer = await complete(
        COACH_SYSTEM,
        coach_user(
            mode=state.get("coach_mode") or "prep_think",
            case=state.get("case") or {},
            transcript=state.get("transcript") or [],
            question=state.get("coach_question") or "",
            highlight=state.get("highlight") or "",
            notes=state.get("notes") or "",
        ),
        temperature=0.5,
    )
    return {"coach_answer": answer}
