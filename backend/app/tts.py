from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import httpx

from .config import (
    APP_TITLE,
    APP_URL,
    CACHE_DIR,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_TTS_MODEL,
    TTS_FALLBACKS,
)

log = logging.getLogger("briefroom.tts")
_preferred_model: str | None = None

ACCENT_HINT = {
    "british": "Speak with a natural British accent. ",
    "australian": "Speak with a natural Australian accent. ",
    "indian": "Speak with a natural Indian English accent. ",
    "irish": "Speak with a natural Irish accent. ",
    "singaporean": "Speak with a natural Singapore English accent. ",
    "south_african": "Speak with a natural South African accent. ",
    "american": "Speak with a natural General American accent. ",
}


AZURE_VOICE = {
    "nova": "en-US-Ava:MAI-Voice-2",
    "shimmer": "en-US-Emma:MAI-Voice-2",
    "echo": "en-US-Andrew:MAI-Voice-2",
    "onyx": "en-US-Brian:MAI-Voice-2",
    "alloy": "en-US-Jenny:MAI-Voice-2",
    "fable": "en-GB-Sonia:MAI-Voice-2",
    "british": "en-GB-Ryan:MAI-Voice-2",
    "indian": "en-IN-Neerja:MAI-Voice-2",
    "australian": "en-AU-Natasha:MAI-Voice-2",
}


def _voice_for(model: str, voice_id: str, accent_id: str) -> str:
    if "mai-voice" in model:
        return AZURE_VOICE.get(accent_id) or AZURE_VOICE.get(voice_id) or "en-US-Ava:MAI-Voice-2"
    return voice_id or "nova"


async def synthesize(
    text: str,
    *,
    voice_id: str = "nova",
    language: str = "en",
    replace: dict | None = None,
    accent_id: str = "american",
    speed: float = 1.0,
) -> bytes:
    hint = ACCENT_HINT.get(accent_id, ACCENT_HINT["american"])
    spoken = text
    if replace:
        for src, dest in replace.items():
            spoken = spoken.replace(src, dest)
    global _preferred_model
    models: list[str] = []
    for slug in [_preferred_model, OPENROUTER_TTS_MODEL, *TTS_FALLBACKS]:
        if slug and slug not in models:
            models.append(slug)
    last_error = ""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": APP_URL,
        "X-Title": APP_TITLE,
    }
    async with httpx.AsyncClient(timeout=45.0) as http:
        for model in models:
            payload: dict = {
                "model": model,
                "input": spoken,
                "voice": _voice_for(model, voice_id, accent_id),
                "response_format": "mp3",
            }
            resp = await http.post(f"{OPENROUTER_BASE_URL}/audio/speech", headers=headers, json=payload)
            if resp.status_code < 400 and resp.content:
                _preferred_model = model
                return resp.content
            last_error = resp.text[:300]
            log.warning("TTS %s failed %s: %s", model, resp.status_code, last_error)
    raise RuntimeError(f"TTS unavailable: {last_error}")


def cache_key(text: str, voice_id: str, accent_id: str) -> str:
    digest = hashlib.sha1(f"{voice_id}|{accent_id}|{text}".encode("utf-8")).hexdigest()
    return digest


def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.mp3"


async def synthesize_cached(
    text: str,
    *,
    voice_id: str = "nova",
    language: str = "en",
    replace: dict | None = None,
    accent_id: str = "american",
) -> tuple[str, bytes]:
    key = cache_key(text, voice_id, accent_id)
    path = cache_path(key)
    if path.exists():
        return key, path.read_bytes()
    audio = await synthesize(
        text,
        voice_id=voice_id,
        language=language,
        replace=replace,
        accent_id=accent_id,
    )
    path.write_bytes(audio)
    return key, audio
