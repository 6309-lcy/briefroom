from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash").strip() or "deepseek/deepseek-v4-flash"
OPENROUTER_MODEL_STRONG = (
    os.getenv("OPENROUTER_MODEL_STRONG", "deepseek/deepseek-v4-pro").strip() or "deepseek/deepseek-v4-pro"
)
OPENROUTER_TTS_MODEL = (
    os.getenv("OPENROUTER_TTS_MODEL", "hexgrad/kokoro-82m").strip() or "hexgrad/kokoro-82m"
)
OPENROUTER_STT_MODEL = (
    os.getenv("OPENROUTER_STT_MODEL", "mistralai/voxtral-mini-3b-2507").strip()
    or "mistralai/voxtral-mini-3b-2507"
)

# Tried in order after the configured model if a slug is geo-blocked or retired.
MODEL_FALLBACKS = [
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-chat",
    "qwen/qwen3.7-flash",
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "mistralai/mistral-small-2603",
]
STRONG_FALLBACKS = [
    "deepseek/deepseek-v4-pro",
    "deepseek/deepseek-chat",
    "qwen/qwen3.7-flash",
]
TTS_FALLBACKS = [
    "hexgrad/kokoro-82m",
    "fish-audio/s2.1-pro-free:free",
    "deepgram/flux-tts:free",
]
STT_FALLBACKS = [
    "mistralai/voxtral-mini-3b-2507",
    "openai/whisper-1",
]
APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8787").strip()
APP_TITLE = "BriefRoom"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8787"))

FRONTEND_DIR = ROOT / "frontend"
CACHE_DIR = ROOT / "backend" / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
