from __future__ import annotations

import logging
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm
from .catalog import INDUSTRIES, catalog_payload, resolve_panelist
from .config import CACHE_DIR, FRONTEND_DIR, OPENROUTER_MODEL, OPENROUTER_MODEL_STRONG
from .graph.graph import run_case, run_coach, run_debrief
from .stt import transcribe
from .pack_pdf import build_pack_pdf, pack_filename
from .store import create_session, get_session, public_session
from .room import Room
from .tts import cache_path, synthesize_cached

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("briefroom")

app = FastAPI(title="BriefRoom", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PanelistIn(BaseModel):
    name: str = "Candidate"
    personality_id: str = "facilitator"
    accent_id: str = "american"
    voice_id: str = "nova"
    interrupt_p: float | None = None
    talkativeness: float | None = None


class SessionIn(BaseModel):
    industry_id: str = "consulting"
    difficulty: str = "standard"
    extra: str = ""
    user_name: str = "You"
    demo: bool = True
    panelists: list[PanelistIn] = Field(default_factory=list)
    prep_seconds: int | None = None
    discussion_seconds: int | None = None
    presentation_seconds: int | None = None


class NotesIn(BaseModel):
    text: str = ""


class CoachIn(BaseModel):
    mode: str = "prep_think"
    question: str = ""
    highlight: str = ""
    notes: str = ""


class TtsIn(BaseModel):
    text: str
    voice_id: str = "nova"
    accent_id: str = "american"
    language: str = "en"


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "has_key": llm.has_key(),
        "provider": "openrouter",
        "model": OPENROUTER_MODEL,
        "model_strong": OPENROUTER_MODEL_STRONG,
    }


@app.get("/api/catalog")
async def catalog():
    return catalog_payload()


@app.post("/api/sessions")
async def start_session(body: SessionIn):
    if not llm.has_key():
        raise HTTPException(400, "Missing OPENROUTER_API_KEY. Copy .env.example to .env.")
    industry = next((i for i in INDUSTRIES if i["id"] == body.industry_id), INDUSTRIES[0])
    raw_panel = [p.model_dump(exclude_none=True) for p in body.panelists] or None
    if not raw_panel:
        from .catalog import DEFAULT_PANEL

        raw_panel = DEFAULT_PANEL
    panelists = [resolve_panelist(item, i) for i, item in enumerate(raw_panel[:3])]
    if body.demo:
        timings = {
            "prep": body.prep_seconds or 120,
            "discussion": body.discussion_seconds or 300,
            "presentation": body.presentation_seconds or 180,
        }
    else:
        timings = {
            "prep": body.prep_seconds or 600,
            "discussion": body.discussion_seconds or 1200,
            "presentation": body.presentation_seconds or 480,
        }
    try:
        result = await run_case(
            {
                "industry_id": industry["id"],
                "industry": industry,
                "difficulty": body.difficulty,
                "extra": body.extra,
                "panelists": panelists,
            }
        )
    except Exception as exc:
        log.exception("case generation failed")
        raise HTTPException(502, f"Case generation failed: {exc}") from exc
    session = create_session(
        {
            "industry": industry,
            "difficulty": body.difficulty,
            "extra": body.extra,
            "user_name": body.user_name or "You",
            "panelists": panelists,
            "case": result.get("case") or {},
            "timings": timings,
            "demo": body.demo,
        }
    )
    return public_session(session)


@app.get("/api/sessions/{sid}/pdf")
async def download_pack(sid: str):
    try:
        session = get_session(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")
    try:
        pdf = build_pack_pdf(session)
    except Exception as exc:
        log.exception("pack pdf failed")
        raise HTTPException(500, f"Could not build PDF: {exc}") from exc
    name = pack_filename(session)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/api/sessions/{sid}")
async def read_session(sid: str):
    try:
        return public_session(get_session(sid))
    except KeyError:
        raise HTTPException(404, "Session not found")


@app.post("/api/sessions/{sid}/notes")
async def save_notes(sid: str, body: NotesIn):
    try:
        session = get_session(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")
    session["notes"] = body.text
    return {"ok": True}


@app.post("/api/sessions/{sid}/coach")
async def coach(sid: str, body: CoachIn):
    try:
        session = get_session(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")
    try:
        result = await run_coach(
            {
                "case": session.get("case") or {},
                "transcript": session.get("transcript") or [],
                "coach_mode": body.mode,
                "coach_question": body.question,
                "highlight": body.highlight,
                "notes": body.notes or session.get("notes") or "",
            }
        )
    except Exception as exc:
        raise HTTPException(502, f"Coach failed: {exc}") from exc
    entry = {
        "mode": body.mode,
        "question": body.question,
        "highlight": body.highlight,
        "answer": result.get("coach_answer") or "",
    }
    session.setdefault("coach_log", []).append(entry)
    return entry


@app.post("/api/sessions/{sid}/debrief")
async def debrief(sid: str):
    try:
        session = get_session(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")
    result = await run_debrief(
        {
            "case": session.get("case") or {},
            "transcript": session.get("transcript") or [],
            "user_name": session.get("user_name") or "You",
            "panelists": session.get("panelists") or [],
        }
    )
    session["debrief"] = result.get("debrief")
    session["phase"] = "debrief"
    return {"debrief": session["debrief"], "session": public_session(session)}


@app.post("/api/stt")
async def stt_endpoint(file: UploadFile = File(...)):
    data = await file.read()
    text = await transcribe(data, filename=file.filename or "clip.webm", content_type=file.content_type or "audio/webm")
    return {"text": text}


@app.post("/api/tts")
async def tts_endpoint(body: TtsIn):
    key, _audio = await synthesize_cached(
        body.text,
        voice_id=body.voice_id,
        language=body.language,
        accent_id=body.accent_id,
    )
    return {"key": key, "url": f"/api/audio/{key}"}


@app.get("/api/audio/{key}")
async def audio(key: str):
    path = cache_path(key)
    if not path.exists():
        raise HTTPException(404, "Audio not found")
    return FileResponse(path, media_type="audio/mpeg")


@app.websocket("/ws/session/{sid}")
async def session_socket(ws: WebSocket, sid: str):
    await ws.accept()
    try:
        session = get_session(sid)
    except KeyError:
        await ws.send_json({"type": "error", "message": "Session not found"})
        await ws.close()
        return
    room = Room(session, ws)
    await room.start()
    try:
        while True:
            msg = await ws.receive_json()
            await room.handle(msg)
    except WebSocketDisconnect:
        await room.close()
    except Exception:
        log.exception("ws failed")
        await room.close()


NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _page(path):
    return FileResponse(path, headers=NO_CACHE)


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.get("/")
async def index():
    page = FRONTEND_DIR / "index.html"
    if not page.exists():
        return JSONResponse({"error": "frontend missing"}, status_code=500)
    return _page(page)


@app.get("/{path:path}")
async def spa(path: str):
    candidate = FRONTEND_DIR / path
    if candidate.exists() and candidate.is_file():
        return _page(candidate)
    page = FRONTEND_DIR / "index.html"
    return _page(page)
