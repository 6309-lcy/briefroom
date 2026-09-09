from __future__ import annotations

import asyncio
from typing import Any

from langgraph.graph import END, START, StateGraph

from .nodes import (
    coach_reply,
    generate_case,
    interrupt_vote,
    panelist_speech,
    pick_interrupt,
    write_debrief,
)
from .state import ACState


def _compile(name: str, node):
    g = StateGraph(ACState)
    g.add_node(name, node)
    g.add_edge(START, name)
    g.add_edge(name, END)
    return g.compile()


ac_case = _compile("generate_case", generate_case)
ac_speech = _compile("panelist_speech", panelist_speech)
ac_debrief = _compile("write_debrief", write_debrief)
ac_coach = _compile("coach_reply", coach_reply)

# One inspectable master graph for the AC lifecycle (docs + debugging).
master = StateGraph(ACState)
master.add_node("generate_case", generate_case)
master.add_node("panelist_speech", panelist_speech)
master.add_node("interrupt_vote", interrupt_vote)
master.add_node("pick_interrupt", pick_interrupt)
master.add_node("write_debrief", write_debrief)
master.add_node("coach_reply", coach_reply)
master.add_edge(START, "generate_case")
master.add_edge("generate_case", END)
ac_graph = master.compile()


async def run_case(payload: dict[str, Any]) -> dict:
    return await ac_case.ainvoke(payload)


async def run_speech(payload: dict[str, Any]) -> dict:
    return await ac_speech.ainvoke(payload)


async def run_interrupt_jury(payload: dict[str, Any]) -> dict:
    """Every other panelist reads the live partial at once, then one may cut in."""
    exclude = payload.get("exclude_id")
    panelists = [p for p in (payload.get("panelists") or []) if p.get("id") != exclude]
    min_words = int(payload.get("min_words") or 12)
    if len((payload.get("user_partial") or "").split()) < min_words:
        return {"chosen": {}, "interrupt_votes": []}
    votes_states = await asyncio.gather(
        *[interrupt_vote({**payload, "speaker_id": p["id"]}) for p in panelists]
    )
    votes: list[dict] = []
    for item in votes_states:
        votes.extend(item.get("interrupt_votes") or [])
    picked = pick_interrupt({"interrupt_votes": votes})
    return {"interrupt_votes": votes, **picked}


async def run_debrief(payload: dict[str, Any]) -> dict:
    return await ac_debrief.ainvoke(payload)


async def run_coach(payload: dict[str, Any]) -> dict:
    return await ac_coach.ainvoke(payload)
