from __future__ import annotations

from typing import Any, Literal, TypedDict


class Turn(TypedDict, total=False):
    id: str
    speaker_id: str
    speaker_name: str
    text: str
    phase: str
    interrupt: bool
    intent: str
    ts: float


class ACState(TypedDict, total=False):
    industry_id: str
    industry: dict
    difficulty: str
    extra: str
    user_name: str
    panelists: list[dict]
    case: dict
    transcript: list[Turn]
    phase: Literal["prep", "discussion", "presentation", "debrief"]
    user_partial: str
    speaker_id: str
    interrupt: bool
    instruction: str
    interrupt_votes: list[dict]
    chosen: dict
    speech: dict
    debrief: dict
    coach_mode: str
    coach_question: str
    highlight: str
    notes: str
    coach_answer: str
