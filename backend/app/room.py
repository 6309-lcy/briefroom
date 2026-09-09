from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from fastapi import WebSocket

from .graph.graph import run_debrief, run_interrupt_jury, run_speech
from .store import add_turn, public_session
from .tts import synthesize_cached

log = logging.getLogger("briefroom.room")

PHASE_ORDER = ["prep", "discussion", "presentation", "debrief"]


def pick_panelist(
    panel: list[dict[str, Any]],
    *,
    prefer: str | None,
    last_speaker: str,
    transcript: list[dict[str, Any]],
    interrupt: bool,
) -> dict[str, Any] | None:
    """Fair rotation: everyone speaks before anyone gets a third turn. Prefer is binding."""
    if not panel:
        return None
    if prefer:
        return next((p for p in panel if p["id"] == prefer), panel[0])
    counts: dict[str, int] = {p["id"]: 0 for p in panel}
    for turn in transcript:
        sid = turn.get("speaker_id")
        if sid in counts:
            counts[sid] += 1
    min_c = min(counts.values()) if counts else 0
    pool = [p for p in panel if counts[p["id"]] == min_c and p["id"] != last_speaker]
    if not pool:
        pool = [p for p in panel if p["id"] != last_speaker]
    if not pool:
        pool = list(panel)
    weights = []
    for p in pool:
        w = 0.35 + float(p.get("talkativeness") or 0.5)
        if interrupt:
            w += float(p.get("interrupt_p") or 0)
        weights.append(max(w, 0.15))
    return random.choices(pool, weights=weights, k=1)[0]


class Room:
    def __init__(self, session: dict[str, Any], ws: WebSocket):
        self.session = session
        self.ws = ws
        self.user_speaking = False
        self.user_partial = ""
        self.busy = False
        self.closed = False
        self.last_speaker = ""
        self.ai_streak = 0
        self.last_interrupt_at = 0.0
        self.last_voice_at = time.time()
        self._scan_task: asyncio.Task | None = None
        self._drive_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._spoken = asyncio.Event()
        self._spoken.set()
        self._pending_cut: dict[str, Any] | None = None
        self._floor_id = ""
        self._live_script = ""
        self._watch_task: asyncio.Task | None = None
        self._clock_task: asyncio.Task | None = None
        self._speech_gen = 0
        self._awaiting_spoken = False
        self.MAX_SILENCE = 5.5
        self.GAP_AFTER_SPEECH = 2.4
        self.session.setdefault("wrapping_up", False)

    async def send(self, payload: dict[str, Any]) -> None:
        if self.closed:
            return
        try:
            await self.ws.send_json(payload)
        except Exception:
            self.closed = True

    async def start(self) -> None:
        await self.send({"type": "hello", "session": public_session(self.session)})
        if self._clock_task is None:
            self._clock_task = asyncio.create_task(self._clock_loop())
        if self.session["phase"] == "discussion":
            self._drive_task = asyncio.create_task(self._driver())
        elif self.session["phase"] == "presentation":
            self._drive_task = asyncio.create_task(self._presentation_loop())

    async def handle(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind == "partial":
            self.user_partial = (msg.get("text") or "").strip()
            self.user_speaking = True
            await self._maybe_scan()
        elif kind == "final":
            text = (msg.get("text") or self.user_partial or "").strip()
            self.user_speaking = False
            self.user_partial = ""
            if text:
                await self._user_turn(text)
        elif kind == "start_speaking":
            self.user_speaking = True
            self.last_voice_at = time.time()
        elif kind == "stop_speaking":
            self.user_speaking = False
            self.last_voice_at = time.time()
        elif kind == "advance":
            await self.advance()
        elif kind == "start_live":
            if self.session["phase"] == "prep":
                await self.advance()
            elif self._drive_task is None and self.session["phase"] == "discussion":
                self._drive_task = asyncio.create_task(self._driver())
            elif self._drive_task is None and self.session["phase"] == "presentation":
                self._drive_task = asyncio.create_task(self._presentation_loop())
        elif kind == "notes":
            self.session["notes"] = msg.get("text") or ""
        elif kind == "speech_done":
            incoming = msg.get("speech_gen")
            if incoming is None or incoming == self._speech_gen:
                self._spoken.set()

    async def close(self) -> None:
        self.closed = True
        for task in (self._scan_task, self._drive_task, self._watch_task, self._clock_task):
            if task:
                task.cancel()

    async def advance(self) -> None:
        phase = self.session["phase"]
        if phase == "prep":
            await self._enter("discussion")
        elif phase == "discussion":
            await self._enter("presentation")
        elif phase == "presentation":
            await self._enter("debrief")
        elif phase == "debrief":
            return

    async def _enter(self, phase: str) -> None:
        timings = self.session.get("timings") or {}
        seconds = int(timings.get(phase) or 0)
        now = time.time()
        self.session["phase"] = phase
        self.session["started_at"] = now
        self.session["phase_started_at"] = now
        self.session["phase_duration"] = seconds
        self.session["phase_ends_at"] = now + seconds if seconds else None
        self.session["remaining_seconds"] = float(seconds)
        self.session["wrapping_up"] = False
        self.session["wrap_spoken"] = False
        self.ai_streak = 0
        self.last_speaker = ""
        self.user_speaking = False
        self.user_partial = ""
        self.busy = False
        self._pending_cut = None
        await self.send(
            {
                "type": "phase",
                "phase": phase,
                "phase_ends_at": self.session["phase_ends_at"],
                "remaining": seconds,
                "session": public_session(self.session),
            }
        )
        if self._clock_task:
            self._clock_task.cancel()
        if phase in ("prep", "discussion", "presentation"):
            self._clock_task = asyncio.create_task(self._clock_loop())
        if phase == "discussion":
            await self._stop_driver()
            self._drive_task = asyncio.create_task(self._driver())
        elif phase == "presentation":
            await self._stop_driver()
            self.last_voice_at = time.time()
            self._drive_task = asyncio.create_task(self._presentation_loop())
        if phase == "debrief":
            await self._run_debrief()

    async def _stop_driver(self) -> None:
        task = self._drive_task
        self._drive_task = None
        if task is None or task.done():
            return
        task.cancel()
        if task is asyncio.current_task():
            return
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

    async def _driver(self) -> None:
        await asyncio.sleep(1.0)
        if not (self.session.get("transcript") or []) and not self.user_speaking:
            try:
                await self._ai_turn(interrupt=False)
            except Exception:
                log.exception("opening turn failed")
        while not self.closed and self.session["phase"] == "discussion":
            if self._remaining() <= 0:
                await self.advance()
                return
            if self.busy or self.user_speaking:
                await asyncio.sleep(0.25)
                continue
            silent = time.time() - self.last_voice_at
            need = self.GAP_AFTER_SPEECH if self.last_speaker == "user" else self.MAX_SILENCE
            if silent < need:
                await asyncio.sleep(0.25)
                continue
            try:
                if self._time_to_wrap() and not self.session.get("wrapping_up"):
                    await self._begin_wrap()
                elif self._wrapping():
                    await asyncio.sleep(0.4)
                else:
                    await self._ai_turn(interrupt=False)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("ai turn failed")
                await self.send({"type": "status", "message": "A panelist lost their words — recovering."})
                self.last_voice_at = time.time()
                await asyncio.sleep(1.2)

    def _order(self) -> list[str]:
        saved = self.session.get("speak_order")
        if saved:
            return list(saved)
        ids = ["user"] + [p["id"] for p in (self.session.get("panelists") or [])]
        self.session["speak_order"] = ids
        return ids

    def _agent_ids(self) -> list[str]:
        """Every AI speaker, wrap-plan order first, then anyone missing."""
        panel = [p["id"] for p in (self.session.get("panelists") or [])]
        planned = [sid for sid in self._order() if sid != "user" and sid in panel]
        for sid in panel:
            if sid not in planned:
                planned.append(sid)
        return planned or panel

    def _name_of(self, sid: str) -> str:
        if sid == "user":
            return self.session.get("user_name") or "You"
        for p in self.session.get("panelists") or []:
            if p["id"] == sid:
                return p["name"]
        return sid

    async def _presentation_loop(self) -> None:
        """Round-robin: every agent, one point per turn, many laps. No interrupts. User optional."""
        await asyncio.sleep(0.8)
        agents = self._agent_ids()
        if not agents:
            return
        chair = self._chair()
        first = self._name_of(agents[0])
        roster = ", then ".join(self._name_of(i) for i in agents)
        try:
            await self._ai_turn(
                interrupt=False,
                speaker_id=chair["id"] if chair else agents[0],
                extra=(
                    "You chair a TEAM presentation. No interrupts. "
                    f"Announce we go around making ONE point each, several times: {roster}. "
                    f"The candidate may add a point when they take the mic; we do not wait. "
                    f"Do not make a content point yet. Pass the mic: I'll pass the mic to {first}."
                ),
            )
        except Exception:
            log.exception("presentation open failed")
        turn_i = 0
        while not self.closed and self.session["phase"] == "presentation":
            if self._remaining() <= 0:
                await self.advance()
                return
            waited = 0.0
            while self.busy and not self.closed and waited < 60:
                await asyncio.sleep(0.2)
                waited += 0.2
            if self.user_speaking:
                slot = time.time() + 8.0
                while self.user_speaking and time.time() < slot and not self.closed:
                    await asyncio.sleep(0.2)
                self.user_speaking = False
            if self.closed or self.session.get("phase") != "presentation":
                return
            if self._remaining() <= 8:
                last = agents[turn_i % len(agents)]
                await self._ai_turn(
                    interrupt=False,
                    speaker_id=last,
                    extra="Time is gone. One closing sentence as a team. Do not pass the mic. No new points.",
                )
                await self.advance()
                return
            sid = agents[turn_i % len(agents)]
            nxt = self._name_of(agents[(turn_i + 1) % len(agents)])
            slice_for = (self.session.get("slices") or {}).get(sid) or ""
            log.info("presentation turn %s -> %s then %s", turn_i, sid, nxt)
            try:
                spoke = await self._ai_turn(
                    interrupt=False,
                    speaker_id=sid,
                    extra=(
                        "PRESENTATION TURN. No interrupts. ONE point only — one or two spoken sentences. "
                        "Do not recap the whole case. Do not give a full speech; you will speak again. "
                        f"Your theme if assigned: {slice_for or 'a new point from the discussion'}. "
                        "Do not repeat a point already made in this presentation. "
                        f"End with: I'll pass the mic to {nxt}."
                    ),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("presentation point failed")
                spoke = False
            turn_i += 1
            await asyncio.sleep(0.35)

    async def _wait_user_slot(self, seconds: float) -> bool:
        deadline = time.time() + seconds
        while not self.closed and time.time() < deadline:
            if self.user_speaking or self.last_speaker == "user":
                break
            await asyncio.sleep(0.25)
        if not (self.user_speaking or self.last_speaker == "user"):
            return False
        while self.user_speaking and not self.closed:
            await asyncio.sleep(0.25)
        return self.last_speaker == "user"

    def _chair(self) -> dict[str, Any] | None:
        panel = self.session.get("panelists") or []
        return next((p for p in panel if p.get("personality_id") == "facilitator"), panel[0] if panel else None)

    def _remaining(self) -> float:
        started = float(self.session.get("phase_started_at") or 0)
        duration = float(self.session.get("phase_duration") or 0)
        if duration <= 0:
            ends = self.session.get("phase_ends_at")
            if not ends:
                return 999.0
            return max(0.0, float(ends) - time.time())
        left = duration - (time.time() - started)
        left = max(0.0, left)
        self.session["remaining_seconds"] = left
        self.session["phase_ends_at"] = started + duration
        return left

    def _time_label(self) -> str:
        left = int(round(self._remaining()))
        m, s = divmod(max(0, left), 60)
        return f"{m}:{s:02d} ({left} seconds)"

    async def _clock_loop(self) -> None:
        while not self.closed and self.session.get("phase") in ("prep", "discussion", "presentation"):
            left = self._remaining()
            await self.send(
                {
                    "type": "clock",
                    "phase": self.session.get("phase"),
                    "remaining": round(left, 1),
                    "wrap_in": max(0, round(left - 30, 1)) if self.session.get("phase") == "discussion" else None,
                }
            )
            if (
                self.session.get("phase") == "discussion"
                and left <= 30
                and not self.session.get("wrapping_up")
                and not self.session.get("wrap_spoken")
            ):
                asyncio.create_task(self._begin_wrap())
            await asyncio.sleep(1.0)

    def _time_to_wrap(self) -> bool:
        return self.session.get("phase") == "discussion" and self._remaining() <= 30.0

    def _wrapping(self) -> bool:
        return self.session.get("phase") == "discussion" and bool(self.session.get("wrapping_up"))

    def _id_from_name(self, raw: str) -> str | None:
        token = (raw or "").strip().lower()
        if not token:
            return None
        if token in {"user", "you", "candidate", (self.session.get("user_name") or "you").lower()}:
            return "user"
        for p in self.session.get("panelists") or []:
            if p["id"].lower() == token or p["name"].lower() == token:
                return p["id"]
            if token in p["name"].lower() or p["name"].split()[0].lower() == token:
                return p["id"]
        return None

    def _apply_plan(self, speech: dict[str, Any]) -> None:
        names = speech.get("speak_order") or []
        ids: list[str] = []
        for name in names:
            sid = self._id_from_name(str(name))
            if sid and sid not in ids:
                ids.append(sid)
        if not ids:
            ids = ["user"] + [p["id"] for p in (self.session.get("panelists") or [])]
        self.session["speak_order"] = ids
        raw_slices = speech.get("slices") or {}
        slices = {}
        if isinstance(raw_slices, dict):
            for key, val in raw_slices.items():
                sid = self._id_from_name(str(key)) or str(key)
                slices[sid] = val
                if sid != str(key):
                    slices[str(key)] = val
        self.session["slices"] = slices
        if speech.get("text"):
            self.session["presentation_plan"] = speech.get("text")

    async def _cut_floor(self) -> None:
        await self.send({"type": "barge_in", "speaker_id": self._pending_cut.get("speaker_id") if self._pending_cut else "cut"})
        self.user_speaking = False
        self.user_partial = ""
        self._spoken.set()

    async def _begin_wrap(self) -> None:
        self.session["wrapping_up"] = True
        if self.session.get("wrap_spoken"):
            return
        if self.busy:
            self._pending_cut = {"kind": "wrap"}
            await self._cut_floor()
            return
        self.session["wrap_spoken"] = True
        chair = self._chair()
        names = ", ".join(p["name"] for p in (self.session.get("panelists") or []))
        user = self.session.get("user_name") or "the candidate"
        await self._ai_turn(
            interrupt=True,
            speaker_id=chair["id"] if chair else None,
            force=True,
            extra=(
                "You are interrupting to WRAP THE DISCUSSION. After you start, nobody else may cut in. "
                "Summarise the points already made. State the emerging recommendation. "
                f"Then assign a presentation order for {user} and {names}: who speaks first, who covers what. "
                "Put that order in speak_order (names) and slices. Do not invite more debate."
            ),
        )

    async def _maybe_scan(self) -> None:
        if self.session.get("phase") != "discussion":
            return
        if self.session.get("wrapping_up"):
            return
        if self._time_to_wrap():
            if self._scan_task and not self._scan_task.done():
                return
            self._scan_task = asyncio.create_task(self._begin_wrap())
            return
        if not self.user_speaking:
            return
        if time.time() - self.last_interrupt_at < 2.4:
            return
        if len(self.user_partial.split()) < 8:
            return
        if self._scan_task and not self._scan_task.done():
            return
        self._scan_task = asyncio.create_task(self._scan_interrupts(self.user_partial, exclude_id="user"))

    async def _scan_interrupts(self, snapshot: str, exclude_id: str) -> None:
        if self.session.get("wrapping_up") or self.session.get("phase") != "discussion":
            return
        try:
            result = await run_interrupt_jury(
                {
                    "panelists": self.session["panelists"],
                    "case": self.session["case"],
                    "transcript": self.session["transcript"],
                    "user_partial": snapshot,
                    "phase": self.session["phase"],
                    "exclude_id": exclude_id,
                    "min_words": 8,
                }
            )
        except Exception:
            log.exception("interrupt jury failed")
            return
        if self.session.get("wrapping_up") or self.session.get("phase") != "discussion":
            return
        chosen = result.get("chosen") or {}
        await self.send({"type": "jury", "votes": result.get("interrupt_votes") or []})
        if not chosen.get("interrupt"):
            return
        self.last_interrupt_at = time.time()
        if self.busy:
            self._pending_cut = {"kind": "interrupt", "speaker_id": chosen["speaker_id"], "partial": snapshot}
            await self._cut_floor()
            return
        if exclude_id == "user" and not self.user_speaking:
            return
        await self._ai_turn(interrupt=True, speaker_id=chosen["speaker_id"], force=True)

    async def _user_turn(self, text: str) -> None:
        turn = add_turn(
            self.session,
            {
                "speaker_id": "user",
                "speaker_name": self.session.get("user_name") or "You",
                "text": text,
                "phase": self.session["phase"],
                "interrupt": False,
                "intent": "user",
            },
        )
        self.last_speaker = "user"
        self.ai_streak = 0
        self.last_voice_at = time.time()
        await self.send({"type": "turn", "turn": turn})

    def _discussion_open(self) -> bool:
        return self.session.get("phase") == "discussion" and not self.session.get("wrapping_up")

    async def _ai_turn(self, *, interrupt: bool, speaker_id: str | None = None, extra: str = "", force: bool = False) -> bool:
        async with self._lock:
            if self.busy and not force:
                return False
            self.busy = True
        spoke = False
        pending = None
        try:
            speaker = self._pick_speaker(prefer=speaker_id, interrupt=interrupt)
            if not speaker:
                return False
            log.info("floor -> %s (%s) interrupt=%s phase=%s", speaker.get("name"), speaker.get("id"), interrupt, self.session.get("phase"))
            instruction = self._instruction(speaker, interrupt)
            if extra:
                instruction = extra + " " + instruction
            instruction = f"OFFICIAL CLOCK: {self._time_label()} remaining. Wrap ONLY if the director says WRAP THE DISCUSSION. If more than 30 seconds remain, do not wrap.\n" + instruction
            result = await run_speech(
                {
                    "panelists": self.session["panelists"],
                    "case": self.session["case"],
                    "transcript": self.session["transcript"],
                    "phase": self.session["phase"],
                    "speaker_id": speaker["id"],
                    "interrupt": interrupt,
                    "user_partial": self.user_partial,
                    "instruction": instruction,
                }
            )
            speech = result.get("speech") or {}
            speech["accent_id"] = speaker.get("accent_id")
            if extra.find("WRAP THE DISCUSSION") >= 0 or (self._time_to_wrap() and (speech.get("intent") or "") == "wrap"):
                self.session["wrapping_up"] = True
                self._apply_plan(speech)
            spoke = await self._emit_speech(speech)
            pending = self._pending_cut
            self._pending_cut = None
        finally:
            self.busy = False
        if pending:
            if pending.get("kind") == "wrap":
                await self._begin_wrap()
            elif pending.get("speaker_id"):
                await self._ai_turn(interrupt=True, speaker_id=pending["speaker_id"], force=True)
        return spoke

    async def _emit_speech(self, speech: dict[str, Any]) -> bool:
        text = (speech.get("text") or "").strip()
        if not text:
            return False
        turn = add_turn(
            self.session,
            {
                "speaker_id": speech.get("speaker_id"),
                "speaker_name": speech.get("speaker_name"),
                "text": text,
                "phase": self.session["phase"],
                "interrupt": bool(speech.get("interrupt")),
                "intent": speech.get("intent") or "structure",
            },
        )
        self.last_speaker = speech.get("speaker_id") or ""
        self.last_voice_at = time.time()
        if speech.get("speaker_id") != "user":
            self.ai_streak += 1
        audio_b64 = ""
        audio_key = ""
        try:
            key, audio = await synthesize_cached(
                text,
                voice_id=speech.get("voice_id") or "nova",
                language=speech.get("tts_language") or "en",
                replace=speech.get("replace") or {},
                accent_id=speech.get("accent_id") or "american",
            )
            import base64

            audio_key = key
            audio_b64 = base64.b64encode(audio).decode("ascii")
        except Exception:
            log.warning("tts failed; browser voice will cover it", exc_info=False)
        words = max(1, len(text.split()))
        timeout = max(4.0, min(28.0, words * 0.42 + 1.5))
        self._floor_id = speech.get("speaker_id") or ""
        self._live_script = text
        self._speech_gen += 1
        gen = self._speech_gen
        self._spoken.clear()
        self._awaiting_spoken = True
        await self.send(
            {
                "type": "turn",
                "turn": turn,
                "interrupt": bool(speech.get("interrupt")),
                "audio_b64": audio_b64,
                "audio_key": audio_key,
                "mime": "audio/mpeg",
                "accent_id": speech.get("accent_id") or "american",
                "voice_id": speech.get("voice_id") or "nova",
                "speech_gen": gen,
            }
        )
        if speech.get("interrupt"):
            await self.send({"type": "barge_in", "speaker_id": speech.get("speaker_id")})
            self.user_speaking = False
            self.user_partial = ""
        if self._discussion_open():
            if self._watch_task:
                self._watch_task.cancel()
            self._watch_task = asyncio.create_task(self._watch_floor(text, self._floor_id))
        try:
            await asyncio.wait_for(self._spoken.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            log.info("speech_done timeout gen=%s speaker=%s", gen, self._floor_id)
            self._spoken.set()
        finally:
            self._awaiting_spoken = False
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
        self._floor_id = ""
        self._live_script = ""
        return True

    async def _watch_floor(self, script: str, speaker_id: str) -> None:
        """Discussion only: others may barge in on a frozen script. Presentation never calls this."""
        started = time.time()
        words = script.split()
        try:
            await asyncio.sleep(0.7)
            while not self.closed and not self._spoken.is_set():
                if not self._discussion_open():
                    return
                if self._time_to_wrap():
                    self.session["wrapping_up"] = True
                    self._pending_cut = {"kind": "wrap"}
                    log.info("clock wrap cut-in at %.0fs left", self._remaining())
                    await self._cut_floor()
                    return
                spoken_n = min(len(words), max(8, int((time.time() - started) / 0.38)))
                prefix = " ".join(words[:spoken_n])
                if time.time() - self.last_interrupt_at < 2.2:
                    await asyncio.sleep(0.5)
                    continue
                result = await run_interrupt_jury(
                    {
                        "panelists": self.session["panelists"],
                        "case": self.session["case"],
                        "transcript": self.session["transcript"],
                        "user_partial": prefix,
                        "phase": "discussion",
                        "exclude_id": speaker_id,
                        "min_words": 8,
                    }
                )
                if not self._discussion_open() or self._spoken.is_set():
                    return
                chosen = result.get("chosen") or {}
                if chosen.get("interrupt") and chosen.get("speaker_id") != speaker_id:
                    log.info("agent interrupt: %s cuts %s", chosen.get("speaker_name"), speaker_id)
                    self.last_interrupt_at = time.time()
                    self._pending_cut = {
                        "kind": "interrupt",
                        "speaker_id": chosen["speaker_id"],
                        "partial": prefix,
                    }
                    await self._cut_floor()
                    return
                await asyncio.sleep(1.1)
        except asyncio.CancelledError:
            return

    async def _run_debrief(self) -> None:
        await self.send({"type": "status", "message": "Assessor is writing your debrief…"})
        try:
            result = await run_debrief(
                {
                    "case": self.session["case"],
                    "transcript": self.session["transcript"],
                    "user_name": self.session.get("user_name") or "You",
                    "panelists": self.session["panelists"],
                }
            )
            self.session["debrief"] = result.get("debrief")
            await self.send(
                {
                    "type": "debrief",
                    "debrief": self.session["debrief"],
                    "session": public_session(self.session),
                }
            )
        except Exception:
            log.exception("debrief failed")
            await self.send({"type": "error", "message": "Assessor debrief failed. Try again from the debrief page."})

    def _pick_speaker(self, prefer: str | None, interrupt: bool) -> dict[str, Any] | None:
        panel = self.session.get("panelists") or []
        return pick_panelist(
            panel,
            prefer=prefer,
            last_speaker=self.last_speaker,
            transcript=self.session.get("transcript") or [],
            interrupt=interrupt,
        )

    def _instruction(self, speaker: dict[str, Any], interrupt: bool) -> str:
        phase = self.session["phase"]
        n = len(self.session.get("transcript") or [])
        if interrupt:
            return (
                "You are cutting in on someone who still has the floor. "
                "Sentence one: react to their live words — agree or disagree, and say why. "
                "Sentence two: one own point. Do not ignore what they were saying."
            )
        if phase == "presentation":
            ask = (self.session.get("case") or {}).get("presentation_ask") or "the recommendation"
            plan = self.session.get("presentation_plan") or ""
            return (
                f"TEAM presentation. No interrupts. Ask: {ask}. Plan: {plan or 'round-robin'}. "
                "ONE point this turn. You will speak multiple times. Pass the mic when done."
            )
        if self._wrapping():
            names = ", ".join(p["name"] for p in (self.session.get("panelists") or []))
            user = self.session.get("user_name") or "the candidate"
            return (
                f"Time is nearly up. WRAP the discussion. No new rabbit holes. "
                f"One-line recommendation, then a presentation order: {user} plus {names} — who covers what. "
                "Do not interrupt anyone after this. Invite moving to the presentation."
            )
        if n == 0:
            return "Open the discussion. Restate the ask in one line, then offer a first cut of the issues."
        if self.last_speaker == "user":
            return "Respond directly to the candidate. Agree, sharpen, or challenge — then add one new point."
        left = int(self._remaining())
        return (
            f"Keep the discussion moving. Official time left: {self._time_label()}. "
            "Do not wrap yet unless told WRAP THE DISCUSSION. Do not repeat the last speaker."
        )

    def _accent(self, speaker_id: str) -> str:
        for p in self.session.get("panelists") or []:
            if p["id"] == speaker_id:
                return p.get("accent_id") or "american"
        return "american"
