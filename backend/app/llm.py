from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from .config import (
    APP_TITLE,
    APP_URL,
    MODEL_FALLBACKS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_MODEL_STRONG,
    STRONG_FALLBACKS,
)

# OpenRouter top_provider limits, fetched 2026-08-23.
# (context_length, max_completion_tokens). None output = unknown, treat as 4096.
MODEL_TOKEN_LIMITS: dict[str, tuple[int, int | None]] = {
    "deepseek/deepseek-v4-flash": (1_024_000, 384_000),
    "deepseek/deepseek-v4-pro": (1_024_000, 384_000),
    "deepseek/deepseek-chat": (128_000, 16_000),
    "qwen/qwen3.7-flash": (1_000_000, 65_536),
    "qwen/qwen-2.5-72b-instruct": (32_768, 16_384),
    "meta-llama/llama-3.3-70b-instruct": (131_072, 16_384),
    "mistralai/mistral-small-2603": (262_144, 16_384),
}
# Unknown slugs and typical :free floors. Tightest configured fallback is 32k/16k.
DEFAULT_TOKEN_LIMITS = (32_768, 4_096)

_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is missing. Copy .env.example to .env and add a key from https://openrouter.ai/keys"
            )
        _client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": APP_URL,
                "X-Title": APP_TITLE,
            },
        )
    return _client


def has_key() -> bool:
    return bool(OPENROUTER_API_KEY)


def _try_next(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "not available in your region",
            "unsupported_country",
            "country, region",
            "not a valid model",
            "invalid model",
            "unknown model",
            "error code: 400",
            "error code: 403",
            "error code: 404",
            "error code: 429",
            "status code: 400",
            "status code: 403",
            "status code: 404",
            "not found",
        )
    )


def _chain(preferred: str | None, extras: list[str]) -> list[str]:
    out: list[str] = []
    for slug in [preferred, *extras]:
        if slug and slug not in out:
            out.append(slug)
    return out


def estimate_tokens(text: str) -> int:
    """Cheap English heuristic. 1 token ≈ 4 chars."""
    return max(1, (len(text or "") + 3) // 4)


def limits_for(slug: str) -> tuple[int, int]:
    ctx, mout = MODEL_TOKEN_LIMITS.get(slug) or DEFAULT_TOKEN_LIMITS
    if slug.endswith(":free") and slug not in MODEL_TOKEN_LIMITS:
        ctx, mout = DEFAULT_TOKEN_LIMITS
    return int(ctx), int(mout or DEFAULT_TOKEN_LIMITS[1])


def chain_limits(preferred: str | None, fallbacks: list[str] | None, *, strong: bool = False) -> tuple[int, int]:
    slugs = _chain(preferred or (OPENROUTER_MODEL_STRONG if strong else OPENROUTER_MODEL), fallbacks or (STRONG_FALLBACKS if strong else MODEL_FALLBACKS))
    ctxs, outs = [], []
    for slug in slugs:
        c, o = limits_for(slug)
        ctxs.append(c)
        outs.append(o)
    return min(ctxs), min(outs)


def input_budget(output_tokens: int, *, strong: bool = False) -> int:
    """Max prompt tokens so prompt + completion stay inside every model in the fallback chain."""
    ctx, mout = chain_limits(None, None, strong=strong)
    out = min(max(256, output_tokens), mout)
    return max(1024, ctx - out - 512)


def fit_prompt(system: str, user: str, output_tokens: int, *, strong: bool = False) -> str:
    """Trim the user message so system + user + completion cannot exceed the chain context."""
    budget = input_budget(output_tokens, strong=strong)
    room = budget - estimate_tokens(system) - 32
    if room < 256:
        room = 256
    if estimate_tokens(user) <= room:
        return user
    chars = max(800, room * 4)
    head = (chars * 3) // 4
    tail = chars - head
    if tail < 200:
        return user[: chars - 1] + "…"
    return user[:head] + "\n\n[...truncated to fit the model context window...]\n\n" + user[-tail:]


async def complete(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1600,
    fallbacks: list[str] | None = None,
) -> str:
    errors: list[str] = []
    for slug in _chain(model or OPENROUTER_MODEL, fallbacks or MODEL_FALLBACKS):
        try:
            ctx, mout = limits_for(slug)
            capped = min(max_tokens, mout)
            room = max(256, ctx - capped - 512 - estimate_tokens(system))
            body = user
            if estimate_tokens(body) > room:
                chars = room * 4
                head = (chars * 3) // 4
                body = user[:head] + "\n\n[...truncated to fit this model's context...]\n\n" + user[-(chars - head) :]
            resp = await client().chat.completions.create(
                model=slug,
                temperature=temperature,
                max_tokens=capped,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": body},
                ],
            )
            choice = resp.choices[0].message if resp.choices else None
            text = ((choice.content if choice else None) or "").strip()
            if text:
                return text
            errors.append(f"{slug}: empty response")
        except Exception as exc:
            errors.append(f"{slug}: {exc}")
            if _try_next(exc):
                continue
            raise
    raise RuntimeError("All OpenRouter chat models failed. " + " | ".join(errors[-3:]))


async def complete_strong(system: str, user: str, *, temperature: float = 0.5, max_tokens: int = 4000) -> str:
    return await complete(
        system,
        user,
        model=OPENROUTER_MODEL_STRONG,
        temperature=temperature,
        max_tokens=max_tokens,
        fallbacks=STRONG_FALLBACKS,
    )


def parse_json(text: str) -> Any:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    else:
        a0 = raw.find("[")
        a1 = raw.rfind("]")
        if a0 >= 0 and a1 > a0:
            raw = raw[a0 : a1 + 1]
    return json.loads(raw)


async def complete_json(
    system: str,
    user: str,
    *,
    strong: bool = False,
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> Any:
    suffix = "\n\nReturn ONLY valid JSON. No markdown fences, no commentary."
    tokens = max_tokens if max_tokens is not None else (4000 if strong else 1600)
    body = fit_prompt(system, user, tokens, strong=strong) + suffix
    if strong:
        text = await complete_strong(system, body, temperature=temperature, max_tokens=tokens)
    else:
        text = await complete(system, body, temperature=temperature, max_tokens=tokens)
    try:
        return parse_json(text)
    except json.JSONDecodeError:
        repair = await complete(
            "You fix malformed or truncated JSON. Return only the full valid JSON object.",
            f"Repair this into valid JSON. If it was cut off, close it sensibly:\n{text[-6000:]}",
            temperature=0,
            max_tokens=min(2000, tokens + 400),
        )
        return parse_json(repair)
