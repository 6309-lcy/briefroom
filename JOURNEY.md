# BriefRoom — demonstrating an AI-powered Assessment Centre

## Problem statement

Graduate and professional hiring still uses **Assessment Centres**: a timed case pack, a group discussion with strangers, a presentation, and an assessor who scores presence, structure, and teamwork.

The problem is you cannot rehearse the thing that actually fails people.

- Mock interviews are 1:1. Real ACs are **multi-party**, with people who talk over you.
- Reading case books does not train **holding the floor** when someone rude cuts in.
- Feedback arrives days later, if at all, and never as a transcript you can interrogate.
- Coaches are expensive. University careers services cannot sit six times a week at a live table.

The opportunity: a rehearsal room that feels like the real table — mixed personalities, mixed accents, live voice, interruption, then a specific debrief.

## What I have built

**BriefRoom** is a browser Assessment Centre:

1. **Setup** — pick an industry (consulting, IB, product, healthcare, FMCG, policy, energy, media). Configure three other candidates: personality, accent, Grok voice.
2. **Prep (10 min, or 2 in demo)** — Grok writes a full pack: client, exhibits, constraints, discussion ask, presentation ask. A coach on the side will teach you how to generate points and how to organise them. It will not dump a model answer.
3. **Group discussion (20 min / 5 demo)** — you speak on the microphone. Three concurrent panelists listen to **live partial transcripts**. Some are kind facilitators. Some will interrupt you, but only if it is in-character *and* the content justifies it.
4. **Group presentation** — the same table presents a recommendation.
5. **Assessor debrief** — a separate LLM, with a hidden rubric from case generation, scores six competencies and quotes you.
6. **Replay coach** — highlight any line in the transcript and ask “how should I have responded?” or “how do I think in this situation?”

The first version ships three panelists (the product supports the same machinery up to six).

## Solution overview — how it works

```
Browser mic ── live partials ──► FastAPI WebSocket room
     │                                  │
     │                         LangGraph nodes
     │                    ┌─────────────┼──────────────┐
     │                    │             │              │
     ▼                    ▼             ▼              ▼
  OpenRouter STT     interrupt      panelist        assessor
  (fallback)           jury          speech          debrief
                          │             │
                          ▼             ▼
                    OpenRouter TTS  audio back to seats
```

**LangGraph, not a single chain.** Each AC job is a compiled subgraph:

| Node | Job |
| --- | --- |
| `generate_case` | Writes the pack + a hidden assessor rubric |
| `interrupt_vote` | One panelist decides whether to barge in on the live partial |
| `pick_interrupt` | Highest urgency that also passes a personality dice roll |
| `panelist_speech` | In-character spoken turn, 2–4 sentences |
| `write_debrief` | Competency scores from the full transcript |
| `coach_reply` | Prep thinking / organisation / better line |

The WebSocket **room** is the conductor: timers, floor, “who speaks next”, audio. It calls graph nodes; it does not pretend to be the model.

**Concurrent LLMs.** While you are still talking, `run_interrupt_jury` fans out one `interrupt_vote` per panelist with `asyncio.gather`. Every bot reads the same incomplete sentence. Only then does a probability prior (rude seats ~0.62, facilitators ~0.08) allow a cut-in. The interruption line has to be about *what you are saying now*.

**Voice.** Panelist audio is OpenRouter TTS (`openai/gpt-4o-mini-tts`) with distinct OpenAI voices (Nova, Shimmer, Echo, Onyx) plus an accent instruction. Your mic uses the Web Speech API for low-latency partials so interruption can happen before you finish the sentence; completed clips can go to OpenRouter STT (`openai/whisper-1`).

**Speaking order.** If you stay quiet, a weighted picker (talkativeness, recency, phase) gives someone else the floor. After two AI turns the room waits longer for you. That is “randomise the order” with a bias, not a round-robin that no real AC uses.

## Use of AI

### AI coding tools used

- **Grok Build (this session)** — architecture, LangGraph graph, FastAPI room, voice wiring, and the frontend.
- Design reference from a UI skill (typography, contrast, no emoji-as-icons, 44px mic target).

### Models, APIs, platforms in the product

| Role | Model / API | Why |
| --- | --- | --- |
| Live panelists, interrupt jury, coach | OpenRouter **openai/gpt-4o-mini** via `https://openrouter.ai/api/v1` chat completions | Latency. Three concurrent votes cannot wait on a slow model. |
| Case writer + assessor | OpenRouter **openai/gpt-4o** (`OPENROUTER_MODEL_STRONG`) | Harder reasoning, hidden rubric, fairer scores. |
| Panelist voices | OpenRouter TTS `POST /audio/speech` | Distinct voices + accent instructions. |
| Accurate fallback transcription | OpenRouter STT `openai/whisper-1` | When Chrome speech recognition is missing. |
| Orchestration | **LangGraph** | Phase + concurrent agents. |
| App | **FastAPI** WebSocket room | Floor, barge-in, timers. |

No API key is ever sent to the browser. TTS and STT are proxied.

### System prompts (examples)

**Case writer** — produces the pack the candidate sees and a rubric they do not:

```
You are a senior Assessment Centre designer for graduate and early-career hiring.
You write realistic group-exercise packs that a real firm would put on the table.

Rules:
- Invent a specific company, numbers, and trade-offs. No generic "Company X".
- The pack must be readable in 8–10 minutes.
- Include at least one uncomfortable trade-off (ethics, politics, short vs long term).
- Do not include a model answer in the candidate-facing materials.
- The hidden rubric is for assessors only.
```

**Panelist** — identity, dialect, and the rule that interruptions must be content-aware:

```
You are {name}, a real candidate in a live Assessment Centre group exercise.
You are NOT an interviewer and you are NOT an AI. Never break character.

Identity:
- Personality: {personality_name} ({tag})
- How you behave: {style}
- Spoken dialect: {dialect}

If you are interrupting:
- Cut in mid-thought. Start with a spoken interruption, then a content-aware point.
- Your reason must be about what they are currently saying, not a random topic change.
```

**Interrupt jury** — every live panelist, in parallel:

```
You are deciding whether {name} would interrupt the candidate who is still talking.
Only interrupt if at least one is true:
- the speaker is factually wrong vs the pack
- they are rambling or hogging
- they are about to land a point {name} wants to steal or correct
Do not interrupt greetings, or the first 8 words of a new turn.

Return JSON: {"interrupt": bool, "urgency": 0-1, "reason": str, "line": str}
```

The room then applies `interrupt_p` as a prior so a kind facilitator almost never fires even if the model is tempted.

**Assessor** — separate model, separate prompt, transcript-only evidence:

```
You are the lead assessor at a professional Assessment Centre.
Score only what is evidenced in the transcript. Quote them. Be kind but not fluffy.
```

**Coach** — used in prep and on highlighted transcript spans:

```
You are a discreet Assessment Centre coach sitting just off-camera.
Offer 2–4 better moves, including an example sentence they could have said.
If they ask about prep, teach how to extract issues, structure, and a point of view
— do not dump a model answer that removes the exercise.
```

Modes: `prep_think`, `prep_organize`, `better_line`, `situation`.

## Impact and value

| Without BriefRoom | With BriefRoom |
| --- | --- |
| One friend playing “bad cop” | Three calibrated personalities, on demand |
| No record of what you said | Full transcript, including who interrupted |
| Vague “speak up more” | Competency scores with quotes |
| Cannot practise interruption | Live barge-in while you are still talking |
| Case books recycle | A new pack per industry, every run |

Who it helps:

- **Students and career-switchers** who get one real AC and cannot afford to waste it.
- **Universities and bootcamps** that need scalable, repeatable group-exercise practice.
- **Firms** that want candidates to fail in rehearsal, not on assessment day.

What “good” looks like in use: you leave with (1) a pack you actually read, (2) a recording-quality transcript of a messy table, (3) three highlighted moments with a better line, (4) one structural habit to change (for example: open with the ask, not your life story).

## What this first version deliberately does not do

- Six seats are in the data model; the UI ships three so the table stays audible.
- True duplex speech-to-speech (a live voice agent per panelist) would be three parallel audio sessions. This version uses **text agents + OpenRouter TTS + live partials**, which already supports rational interruption and is cheaper to run.
- There is no login or history store. Sessions live in memory for the demo.

Those are the next two steps, not blockers for a working rehearsal.
