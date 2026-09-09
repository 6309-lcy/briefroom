from __future__ import annotations

import logging

import httpx

from .config import (
    APP_TITLE,
    APP_URL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_STT_MODEL,
    STT_FALLBACKS,
)

log = logging.getLogger("briefroom.stt")


def _audio_format(filename: str, content_type: str) -> str:
    name = (filename or "").lower()
    mime = (content_type or "").lower()
    for ext in ("webm", "wav", "mp3", "mp4", "m4a", "ogg", "flac"):
        if name.endswith(f".{ext}") or ext in mime:
            return ext
    return "webm"


async def transcribe(data: bytes, filename: str = "clip.webm", content_type: str = "audio/webm") -> str:
    import base64

    fmt = _audio_format(filename, content_type)
    models: list[str] = []
    for slug in [OPENROUTER_STT_MODEL, *STT_FALLBACKS]:
        if slug and slug not in models:
            models.append(slug)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": APP_URL,
        "X-Title": APP_TITLE,
    }
    last = ""
    async with httpx.AsyncClient(timeout=60.0) as http:
        for model in models:
            payload = {
                "model": model,
                "input_audio": {
                    "data": base64.b64encode(data).decode("ascii"),
                    "format": fmt,
                },
            }
            resp = await http.post(
                f"{OPENROUTER_BASE_URL}/audio/transcriptions",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code >= 400:
                files = {"file": (filename, data, content_type)}
                resp = await http.post(
                    f"{OPENROUTER_BASE_URL}/audio/transcriptions",
                    headers=headers,
                    data={"model": model, "language": "en"},
                    files=files,
                )
            if resp.status_code < 400:
                return (resp.json().get("text") or "").strip()
            last = resp.text[:300]
            log.warning("STT %s failed %s: %s", model, resp.status_code, last)
            if resp.status_code not in (400, 403, 404):
                resp.raise_for_status()
    raise RuntimeError(f"STT unavailable: {last}")
