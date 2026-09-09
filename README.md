# BriefRoom

A voice Assessment Centre rehearsal. You sit with three AI candidates, study a generated case pack, then talk — they can interrupt you — and an assessor writes a debrief from the transcript.

## GitHub Pages (no server)

This is a **static site**. No Python, no FastAPI, nothing to host except GitHub Pages.

Live at **https://6309-lcy.github.io/briefroom/**

1. Open Settings (top right).
2. Paste your [OpenRouter API key](https://openrouter.ai/keys).
3. Pick a live model and a strong model.
4. Issue the pack.

The browser talks to OpenRouter directly. The key stays **in this tab only** — refresh clears it. Chrome is best (live speech recognition). Hold **Space** or the mic.

## Why LangGraph

The Assessment Centre is a **state machine with concurrent agents**, not a single chatbot:

- **Phases** — prep → group discussion → presentation → assessor debrief
- **Concurrent panelists** — three personalities read your live partial transcript at once and vote on whether to cut in
- **Named jobs** — case writer, speaker, interrupt jury, assessor, coach are separate graph nodes

LangChain chains would flatten this. LangGraph keeps each role as a node you can invoke from the live WebSocket room.

## Stack

| Layer | Choice |
| --- | --- |
| Orchestration | LangGraph |
| Reasoning | OpenRouter `openai/gpt-4o-mini` (live panelists) and `openai/gpt-4o` (case + assessor) |
| Voice out | OpenRouter TTS (`/audio/speech`, `openai/gpt-4o-mini-tts`) |
| Voice in | Browser Speech Recognition for live partials, OpenRouter STT (`openai/whisper-1`) as fallback |
| App | FastAPI + WebSocket + a static frontend |

## Run

```powershell
cd ploymer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# paste OPENROUTER_API_KEY from https://openrouter.ai/keys
python run.py
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787). Chrome is best (live speech recognition). Hold **Space** or click the mic.

Demo timings (default): 2 min prep / 5 min discussion / 3 min presentation. Uncheck the box for a full 10 / 20 / 8.

## Flow

1. Pick an industry. Customise three seats: personality, accent, voice.
2. Study the generated pack. Ask the prep coach how to think or how to organise notes.
3. Enter the table. Panelists speak with their own voice. A rude seat can barge in while you are talking.
4. Move to a group presentation, then receive an assessor debrief.
5. Highlight any line in the transcript and ask how you should have handled it.

See [JOURNEY.md](JOURNEY.md) for the problem, architecture, system prompts, and impact write-up.
