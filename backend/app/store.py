from __future__ import annotations

import time
import uuid
from typing import Any

SESSIONS: dict[str, dict[str, Any]] = {}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def create_session(data: dict[str, Any]) -> dict[str, Any]:
    sid = new_id()
    now = time.time()
    timings = data.get("timings") or {}
    prep_secs = int(timings.get("prep") or 0)
    session = {
        "id": sid,
        "created_at": now,
        "phase": "prep",
        "transcript": [],
        "notes": "",
        "coach_log": [],
        "debrief": None,
        "started_at": now,
        "phase_started_at": now,
        "phase_duration": prep_secs,
        "phase_ends_at": now + prep_secs if prep_secs else None,
        "remaining_seconds": float(prep_secs),
        **data,
    }
    SESSIONS[sid] = session
    return session


def get_session(sid: str) -> dict[str, Any]:
    session = SESSIONS.get(sid)
    if not session:
        raise KeyError(sid)
    return session


def add_turn(session: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    turn = {"id": new_id(), "ts": time.time(), **turn}
    session["transcript"].append(turn)
    return turn


def public_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session["id"],
        "phase": session["phase"],
        "industry": session.get("industry"),
        "user_name": session.get("user_name"),
        "panelists": session.get("panelists"),
        "case": _public_case(session.get("case") or {}),
        "timings": session.get("timings"),
        "transcript": session.get("transcript") or [],
        "notes": session.get("notes") or "",
        "debrief": session.get("debrief"),
        "coach_log": session.get("coach_log") or [],
        "phase_ends_at": session.get("phase_ends_at"),
        "started_at": session.get("started_at"),
        "phase_duration": session.get("phase_duration"),
        "remaining_seconds": session.get("remaining_seconds"),
    }


def _public_case(case: dict[str, Any]) -> dict[str, Any]:
    hidden = dict(case)
    hidden.pop("hidden_rubric", None)
    return hidden
