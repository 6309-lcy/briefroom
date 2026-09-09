/* Client-side BriefRoom: OpenRouter from the browser. Key lives in memory only. */
(function (global) {
  const MODELS = [
    { id: "deepseek/deepseek-v4-flash", label: "DeepSeek V4 Flash (fast)" },
    { id: "deepseek/deepseek-v4-pro", label: "DeepSeek V4 Pro (strong)" },
    { id: "deepseek/deepseek-chat", label: "DeepSeek Chat" },
    { id: "qwen/qwen3.7-flash", label: "Qwen 3.7 Flash" },
    { id: "qwen/qwen-2.5-72b-instruct", label: "Qwen 2.5 72B" },
    { id: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B" },
    { id: "mistralai/mistral-small-2603", label: "Mistral Small" },
    { id: "openai/gpt-4o-mini", label: "GPT-4o mini" },
    { id: "openai/gpt-4o", label: "GPT-4o" },
    { id: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
    { id: "anthropic/claude-sonnet-4", label: "Claude Sonnet 4" },
  ];
  const TTS_MODELS = [
    { id: "hexgrad/kokoro-82m", label: "Kokoro" },
    { id: "openai/gpt-4o-mini-tts", label: "OpenAI TTS" },
    { id: "browser", label: "Browser voice only" },
  ];

  const settings = {
    apiKey: "",
    model: "deepseek/deepseek-v4-flash",
    modelStrong: "deepseek/deepseek-v4-pro",
    ttsModel: "hexgrad/kokoro-82m",
  };

  function setSettings(partial) {
    if (partial.apiKey !== undefined) settings.apiKey = String(partial.apiKey || "").trim();
    if (partial.model) settings.model = partial.model.trim();
    if (partial.modelStrong) settings.modelStrong = partial.modelStrong.trim();
    if (partial.ttsModel) settings.ttsModel = partial.ttsModel.trim();
  }

  function byId(rows, id) {
    return (rows || []).find((r) => r.id === id);
  }

  function resolvePanelist(raw, slot) {
    const cat = global.BRIEF_CATALOG;
    const personality = byId(cat.personalities, raw.personality_id) || cat.personalities[0];
    const accent = byId(cat.accents, raw.accent_id) || cat.accents[0];
    const voice = byId(cat.voices, raw.voice_id) || cat.voices[0];
    const name = (raw.name || `Candidate ${slot + 1}`).trim();
    const num = (key, fallback) => {
      const v = raw[key];
      if (v === undefined || v === null || v === "") return fallback;
      return Number(v);
    };
    return {
      id: `p${slot}`,
      slot,
      name,
      personality_id: personality.id,
      personality_name: personality.name,
      tag: personality.tag,
      summary: personality.summary,
      interrupt_p: num("interrupt_p", personality.interrupt_p),
      talkativeness: num("talkativeness", personality.talkativeness),
      style: personality.style,
      accent_id: accent.id,
      accent_name: accent.name,
      tts_language: accent.tts_language,
      dialect: accent.dialect,
      replace: accent.replace || {},
      voice_id: voice.id,
      voice_name: voice.name,
      voice_tone: voice.tone,
    };
  }

  function parseJson(text) {
    let raw = (text || "").trim();
    if (raw.startsWith("```")) raw = raw.replace(/^```(?:json)?\s*/, "").replace(/\s*```$/, "");
    const a = raw.indexOf("{");
    const b = raw.lastIndexOf("}");
    if (a >= 0 && b > a) raw = raw.slice(a, b + 1);
    return JSON.parse(raw);
  }

  async function chat({ system, user, strong, maxTokens, temperature }) {
    if (!settings.apiKey) throw new Error("Paste your OpenRouter API key in Settings.");
    const model = strong ? settings.modelStrong : settings.model;
    const resp = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${settings.apiKey}`,
        "Content-Type": "application/json",
        "HTTP-Referer": location.origin,
        "X-Title": "BriefRoom",
      },
      body: JSON.stringify({
        model,
        temperature: temperature ?? 0.7,
        max_tokens: maxTokens ?? 1600,
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = data.error?.message || data.message || resp.statusText;
      throw new Error(msg || `OpenRouter ${resp.status}`);
    }
    return (data.choices?.[0]?.message?.content || "").trim();
  }

  async function chatJson(opts) {
    const text = await chat({
      ...opts,
      user: (opts.user || "") + "\n\nReturn ONLY valid JSON. No markdown fences, no commentary.",
    });
    try {
      return parseJson(text);
    } catch (_) {
      const repair = await chat({
        system: "You fix malformed JSON. Return only valid JSON.",
        user: "Repair:\n" + text.slice(-8000),
        strong: opts.strong,
        maxTokens: 2000,
        temperature: 0,
      });
      return parseJson(repair);
    }
  }

  async function ttsToB64(text, voiceId) {
    if (!settings.apiKey || settings.ttsModel === "browser") return "";
    try {
      const resp = await fetch("https://openrouter.ai/api/v1/audio/speech", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${settings.apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": location.origin,
          "X-Title": "BriefRoom",
        },
        body: JSON.stringify({
          model: settings.ttsModel,
          input: text,
          voice: voiceId || "nova",
        }),
      });
      if (!resp.ok) return "";
      const buf = await resp.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let bin = "";
      for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
      return btoa(bin);
    } catch (_) {
      return "";
    }
  }

  const CASE_SYSTEM = `You are a senior Assessment Centre designer for graduate and early-career hiring.
You write realistic group-exercise packs that a real firm would put on the table.
Rules:
- Invent a specific company, numbers, and trade-offs. No generic "Company X".
- The pack must be readable in 8–10 minutes.
- Include at least one uncomfortable trade-off.
- Do not include a model answer in the candidate-facing materials.
- The hidden rubric is for assessors only.
Return JSON with: title, client, industry_label, setting, timebox, objective, brief, exhibits (array of {name, kind, body}), constraints, discussion_ask, presentation_ask, hidden_rubric {what_good_looks_like, common_traps, must_hit_points}.
Brief 250–350 words. 3–4 exhibits with real figures.`;

  function panelistSystem(p) {
    return `You are ${p.name}, a real candidate in a live Assessment Centre group exercise.
You are NOT an interviewer and you are NOT an AI. Never break character.
Personality: ${p.personality_name} (${p.tag}). ${p.style}
Spoken dialect: ${p.dialect}
Keep each turn to 2–4 spoken sentences (under 80 words) unless presenting.
If interrupting: sentence 1 MUST react to the live unfinished words, then one own point.
If presenting: ONE point per turn. Pass the mic. No interrupts.
Do not wrap unless the director says WRAP THE DISCUSSION.`;
  }

  function transcriptBlock(turns, limit) {
    const rows = (turns || []).slice(-(limit || 40));
    if (!rows.length) return "(The room is silent.)";
    return rows
      .map((t) => `${t.speaker_name}:${t.interrupt ? " [INTERRUPT]" : ""} ${t.text}`)
      .join("\n");
  }

  function exhibitsOf(c) {
    return (c.exhibits || [])
      .map((e) => `### ${e.name} (${e.kind})\n${String(e.body || "").slice(0, 480)}`)
      .join("\n\n");
  }

  function pickPanelist(panel, prefer, last, transcript) {
    if (!panel.length) return null;
    if (prefer) return panel.find((p) => p.id === prefer) || panel[0];
    const counts = Object.fromEntries(panel.map((p) => [p.id, 0]));
    for (const t of transcript || []) if (counts[t.speaker_id] !== undefined) counts[t.speaker_id]++;
    const minC = Math.min(...Object.values(counts));
    let pool = panel.filter((p) => counts[p.id] === minC && p.id !== last);
    if (!pool.length) pool = panel.filter((p) => p.id !== last);
    if (!pool.length) pool = panel;
    const weights = pool.map((p) => Math.max(0.15, 0.35 + (p.talkativeness || 0.5)));
    const sum = weights.reduce((a, b) => a + b, 0);
    let r = Math.random() * sum;
    for (let i = 0; i < pool.length; i++) {
      r -= weights[i];
      if (r <= 0) return pool[i];
    }
    return pool[pool.length - 1];
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  class Engine {
    constructor(onMsg) {
      this.onMsg = onMsg;
      this.session = null;
      this.busy = false;
      this.userSpeaking = false;
      this.userPartial = "";
      this.lastSpeaker = "";
      this.lastVoiceAt = Date.now();
      this.lastInterruptAt = 0;
      this.closed = false;
      this.speechGen = 0;
      this._spoken = null;
      this._drive = 0;
    }

    emit(msg) {
      this.onMsg && this.onMsg(msg);
    }

    send(type, extra) {
      this.emit(Object.assign({ type, session: this.publicSession() }, extra || {}));
    }

    publicSession() {
      const s = this.session;
      if (!s) return null;
      const copy = Object.assign({}, s);
      if (copy.case) {
        copy.case = Object.assign({}, copy.case);
        delete copy.case.hidden_rubric;
      }
      return copy;
    }

    remaining() {
      const s = this.session;
      const started = s.phase_started_at || 0;
      const duration = s.phase_duration || 0;
      if (duration <= 0) return 999;
      return Math.max(0, duration - (Date.now() / 1000 - started));
    }

    async createSession(form) {
      const cat = global.BRIEF_CATALOG;
      const industry = byId(cat.industries, form.industry_id) || cat.industries[0];
      const panelists = (form.panelists || cat.default_panel).slice(0, 3).map((p, i) => resolvePanelist(p, i));
      const demo = !!form.demo;
      const timings = demo
        ? { prep: 120, discussion: 300, presentation: 180 }
        : { prep: 600, discussion: 1200, presentation: 480 };
      const casePack = await chatJson({
        system: CASE_SYSTEM,
        user: `Industry track: ${industry.name} (${industry.id}).\nFlavour: ${industry.blurb}\nDifficulty: ${form.difficulty || "standard"}.\nExtra: ${form.extra || "none"}.\nDesign one self-contained group case.`,
        strong: true,
        maxTokens: 7000,
        temperature: 0.7,
      });
      casePack.industry_label = casePack.industry_label || industry.name;
      const now = Date.now() / 1000;
      this.session = {
        id: "local-" + Math.random().toString(36).slice(2, 10),
        phase: "prep",
        user_name: form.user_name || "You",
        industry,
        panelists,
        case: casePack,
        transcript: [],
        notes: "",
        timings,
        phase_started_at: now,
        phase_duration: timings.prep,
        phase_ends_at: now + timings.prep,
        remaining_seconds: timings.prep,
        wrapping_up: false,
        wrap_spoken: false,
      };
      return this.publicSession();
    }

    handle(msg) {
      const kind = msg.type;
      if (kind === "partial") {
        this.userPartial = (msg.text || "").trim();
        this.userSpeaking = true;
        this._maybeScan();
      } else if (kind === "final") {
        const text = (msg.text || this.userPartial || "").trim();
        this.userSpeaking = false;
        this.userPartial = "";
        if (text) this._userTurn(text);
      } else if (kind === "start_speaking") {
        this.userSpeaking = true;
        this.lastVoiceAt = Date.now();
      } else if (kind === "stop_speaking") {
        this.userSpeaking = false;
        this.lastVoiceAt = Date.now();
      } else if (kind === "advance") {
        this.advance();
      } else if (kind === "start_live") {
        if (this.session.phase === "prep") this.advance();
        else this._startDriver();
      } else if (kind === "notes") {
        this.session.notes = msg.text || "";
      } else if (kind === "speech_done") {
        if (this._spoken && (msg.speech_gen == null || msg.speech_gen === this.speechGen)) {
          this._spoken();
          this._spoken = null;
        }
      }
    }

    async advance() {
      const phase = this.session.phase;
      if (phase === "prep") await this._enter("discussion");
      else if (phase === "discussion") await this._enter("presentation");
      else if (phase === "presentation") await this._enter("debrief");
    }

    async _enter(phase) {
      const seconds = (this.session.timings || {})[phase] || 0;
      const now = Date.now() / 1000;
      this.session.phase = phase;
      this.session.phase_started_at = now;
      this.session.phase_duration = seconds;
      this.session.phase_ends_at = now + seconds;
      this.session.remaining_seconds = seconds;
      this.session.wrapping_up = false;
      this.userSpeaking = false;
      this.busy = false;
      this.lastSpeaker = "";
      this._drive += 1;
      this.send("phase", { phase, phase_ends_at: this.session.phase_ends_at, remaining: seconds });
      if (phase === "discussion") this._driver(this._drive);
      else if (phase === "presentation") this._presentation(this._drive);
      else if (phase === "debrief") await this._debrief();
      this._clock(this._drive);
    }

    _startDriver() {
      if (this.session.phase === "discussion") this._driver(this._drive);
      if (this.session.phase === "presentation") this._presentation(this._drive);
    }

    async _clock(token) {
      while (!this.closed && token === this._drive && ["prep", "discussion", "presentation"].includes(this.session.phase)) {
        const left = this.remaining();
        this.session.remaining_seconds = left;
        this.send("clock", { phase: this.session.phase, remaining: Math.round(left * 10) / 10 });
        if (this.session.phase === "discussion" && left <= 30 && !this.session.wrapping_up) {
          this._beginWrap();
        }
        await sleep(1000);
      }
    }

    async _driver(token) {
      await sleep(1000);
      if (!this.session.transcript.length && !this.userSpeaking) {
        try {
          await this._aiTurn(false);
        } catch (e) {
          this.send("status", { message: "A panelist lost their words — recovering." });
        }
      }
      while (!this.closed && token === this._drive && this.session.phase === "discussion") {
        if (this.remaining() <= 0) {
          await this.advance();
          return;
        }
        if (this.busy || this.userSpeaking) {
          await sleep(250);
          continue;
        }
        const silent = (Date.now() - this.lastVoiceAt) / 1000;
        const need = this.lastSpeaker === "user" ? 2.4 : 5.5;
        if (silent < need) {
          await sleep(250);
          continue;
        }
        try {
          if (this.remaining() <= 30 && !this.session.wrapping_up) await this._beginWrap();
          else if (!this.session.wrapping_up) await this._aiTurn(false);
          else await sleep(400);
        } catch (e) {
          this.send("status", { message: "A panelist lost their words — recovering." });
          this.lastVoiceAt = Date.now();
          await sleep(1200);
        }
      }
    }

    _agentIds() {
      const panel = this.session.panelists || [];
      const order = this.session.speak_order || ["user", ...panel.map((p) => p.id)];
      const planned = order.filter((id) => id !== "user" && panel.some((p) => p.id === id));
      for (const p of panel) if (!planned.includes(p.id)) planned.push(p.id);
      return planned;
    }

    async _presentation(token) {
      await sleep(800);
      const agents = this._agentIds();
      if (!agents.length) return;
      const chair = this.session.panelists.find((p) => p.personality_id === "facilitator") || this.session.panelists[0];
      const roster = agents.map((id) => this._nameOf(id)).join(", then ");
      try {
        await this._aiTurn(false, chair.id, `You chair a TEAM presentation. No interrupts. Announce we go around making ONE point each: ${roster}. Do not make a content point yet. Pass the mic to ${this._nameOf(agents[0])}.`);
      } catch (_) {}
      let turnI = 0;
      while (!this.closed && token === this._drive && this.session.phase === "presentation") {
        if (this.remaining() <= 0) {
          await this.advance();
          return;
        }
        let waited = 0;
        while (this.busy && waited < 60 && token === this._drive) {
          await sleep(200);
          waited += 0.2;
        }
        if (this.userSpeaking) {
          const until = Date.now() + 8000;
          while (this.userSpeaking && Date.now() < until) await sleep(200);
          this.userSpeaking = false;
        }
        if (this.remaining() <= 8) {
          await this._aiTurn(false, agents[turnI % agents.length], "Time is gone. One closing sentence as a team.");
          await this.advance();
          return;
        }
        const sid = agents[turnI % agents.length];
        const nxt = this._nameOf(agents[(turnI + 1) % agents.length]);
        try {
          await this._aiTurn(false, sid, `PRESENTATION TURN. ONE point only. End with: I'll pass the mic to ${nxt}.`);
        } catch (_) {}
        turnI += 1;
        await sleep(350);
      }
    }

    _nameOf(sid) {
      if (sid === "user") return this.session.user_name || "You";
      const p = (this.session.panelists || []).find((x) => x.id === sid);
      return p ? p.name : sid;
    }

    async _beginWrap() {
      if (this.session.wrap_spoken) return;
      this.session.wrapping_up = true;
      this.session.wrap_spoken = true;
      const chair = this.session.panelists.find((p) => p.personality_id === "facilitator") || this.session.panelists[0];
      const names = this.session.panelists.map((p) => p.name).join(", ");
      await this._aiTurn(
        true,
        chair.id,
        `You are interrupting to WRAP THE DISCUSSION. Summarise, state the emerging recommendation, then assign a presentation order for ${this.session.user_name} and ${names}. Put names in speak_order and slices.`
      );
    }

    _maybeScan() {
      if (this.session.phase !== "discussion" || this.session.wrapping_up) return;
      if (Date.now() - this.lastInterruptAt < 2400) return;
      if (this.userPartial.split(/\s+/).filter(Boolean).length < 8) return;
      this._scanInterrupts(this.userPartial, "user");
    }

    async _scanInterrupts(snapshot, excludeId) {
      if (this.session.phase !== "discussion" || this.session.wrapping_up) return;
      const others = this.session.panelists.filter((p) => p.id !== excludeId);
      const votes = await Promise.all(others.map((p) => this._interruptVote(p, snapshot)));
      const yes = votes.filter((v) => v.interrupt).sort((a, b) => b.urgency - a.urgency);
      this.send("jury", { votes });
      if (!yes.length) return;
      this.lastInterruptAt = Date.now();
      await this._aiTurn(true, yes[0].speaker_id);
    }

    async _interruptVote(p, partial) {
      const words = (partial || "").trim().split(/\s+/).filter(Boolean).length;
      if (words < 8) return { speaker_id: p.id, interrupt: false, urgency: 0 };
      try {
        const data = await chatJson({
          system: `You decide if ${p.name} interrupts. Personality: ${p.personality_name}. ${p.style} Interrupt tendency ${(p.interrupt_p * 100).toFixed(0)}%. If tendency >= 40%, lean YES when you disagree. Return JSON {interrupt, urgency, reason, line}.`,
          user: `Case: ${this.session.case.title}\nLIVE words:\n"""${partial}"""\nWould ${p.name} cut in?`,
          temperature: 0.3,
          maxTokens: 400,
        });
        let interrupt = !!data.interrupt;
        const urgency = Number(data.urgency || 0);
        const prior = p.interrupt_p || 0;
        if (interrupt && urgency < 0.22) interrupt = false;
        else if (interrupt && Math.random() > Math.min(0.98, 0.5 + prior * 0.8)) interrupt = false;
        else if (!interrupt && prior >= 0.45 && words >= 10 && Math.random() < prior * 0.55) interrupt = true;
        return { speaker_id: p.id, speaker_name: p.name, interrupt, urgency, line: data.line || "" };
      } catch (_) {
        return { speaker_id: p.id, interrupt: false, urgency: 0 };
      }
    }

    _userTurn(text) {
      const turn = {
        id: "t" + Date.now(),
        speaker_id: "user",
        speaker_name: this.session.user_name || "You",
        text,
        phase: this.session.phase,
        interrupt: false,
      };
      this.session.transcript.push(turn);
      this.lastSpeaker = "user";
      this.lastVoiceAt = Date.now();
      this.send("turn", { turn });
    }

    async _aiTurn(interrupt, speakerId, extra) {
      if (this.busy && !interrupt) return false;
      this.busy = true;
      try {
        const speaker = pickPanelist(this.session.panelists, speakerId, this.lastSpeaker, this.session.transcript);
        if (!speaker) return false;
        const left = this.remaining();
        const m = Math.floor(left / 60);
        const s = String(Math.round(left % 60)).padStart(2, "0");
        let instruction = extra || "Take the floor and move the discussion forward.";
        instruction = `OFFICIAL CLOCK: ${m}:${s} remaining. Wrap ONLY if told WRAP THE DISCUSSION.\n` + instruction;
        const c = this.session.case;
        const data = await chatJson({
          system: panelistSystem(speaker),
          user: `Case: ${c.title}\nClient: ${c.client}\nAsk: ${c.discussion_ask}\nBrief:\n${c.brief}\nExhibits:\n${exhibitsOf(c)}\nPhase: ${this.session.phase}\nInterrupting: ${interrupt}\nLive words: ${this.userPartial || "(none)"}\nDirector: ${instruction}\nRecent:\n${transcriptBlock(this.session.transcript)}\nSpeak as ${speaker.name}. JSON: {"text":"...","intent":"agree|challenge|structure|present|interrupt|wrap","speak_order":[],"slices":{}}`,
          temperature: 0.85,
          maxTokens: 500,
        });
        const text = (data.text || "").trim();
        if (!text) return false;
        if (String(extra || "").includes("WRAP THE DISCUSSION") && Array.isArray(data.speak_order) && data.speak_order.length) {
          this.session.speak_order = data.speak_order.map((n) => this._idFromName(n)).filter(Boolean);
          this.session.slices = data.slices || {};
        }
        const turn = {
          id: "t" + Date.now(),
          speaker_id: speaker.id,
          speaker_name: speaker.name,
          text,
          phase: this.session.phase,
          interrupt: !!interrupt,
        };
        this.session.transcript.push(turn);
        this.lastSpeaker = speaker.id;
        this.lastVoiceAt = Date.now();
        this.speechGen += 1;
        const gen = this.speechGen;
        const audio_b64 = await ttsToB64(text, speaker.voice_id);
        const wait = new Promise((resolve) => {
          this._spoken = resolve;
          setTimeout(resolve, Math.min(28000, 1500 + text.split(/\s+/).length * 420));
        });
        this.send("turn", {
          turn,
          interrupt: !!interrupt,
          audio_b64,
          accent_id: speaker.accent_id,
          voice_id: speaker.voice_id,
          speech_gen: gen,
        });
        if (interrupt) {
          this.userSpeaking = false;
          this.userPartial = "";
          this.send("barge_in", { speaker_id: speaker.id });
        }
        if (this.session.phase === "discussion" && !this.session.wrapping_up) {
          this._watchFloor(text, speaker.id);
        }
        await wait;
        this._spoken = null;
        return true;
      } finally {
        this.busy = false;
      }
    }

    _idFromName(raw) {
      const token = String(raw || "").trim().toLowerCase();
      if (!token) return null;
      if (["user", "you", "candidate", (this.session.user_name || "you").toLowerCase()].includes(token)) return "user";
      for (const p of this.session.panelists) {
        if (p.id.toLowerCase() === token || p.name.toLowerCase() === token) return p.id;
        if (p.name.toLowerCase().startsWith(token) || token.includes(p.name.split(" ")[0].toLowerCase())) return p.id;
      }
      return null;
    }

    async _watchFloor(script, speakerId) {
      await sleep(700);
      if (this.session.phase !== "discussion") return;
      const words = script.split(/\s+/);
      if (words.length < 8) return;
      await this._scanInterrupts(words.slice(0, Math.min(words.length, 24)).join(" "), speakerId);
    }

    async _debrief() {
      this.send("status", { message: "Assessor is writing your debrief…" });
      const c = this.session.case;
      const userName = this.session.user_name || "You";
      const packed = (this.session.transcript || [])
        .slice(-40)
        .map((t) => `${t.speaker_name}: ${String(t.text || "").slice(0, 220)}`)
        .join("\n");
      try {
        const evidence = await chatJson({
          system: "Extract Assessment Centre evidence for ONE candidate (the user). Return JSON {speaking_pattern, quotes:[{text,phase,why_it_matters}], pack_use, team_moves, pressure, misses}.",
          user: `Candidate: ${userName}\nCase: ${c.title}\nAsk: ${c.discussion_ask}\nRubric: ${JSON.stringify(c.hidden_rubric || {})}\nTranscript:\n${packed}`,
          strong: true,
          maxTokens: 2200,
          temperature: 0.3,
        });
        const scoreSys =
          "Score THREE competencies. JSON {competencies:[{id,label,score,note}]}. Integers 1-5. Quote them in the note.";
        const content = await chatJson({
          system: scoreSys,
          user: `Score structure, commercial, insight.\nCandidate ${userName}. Evidence: ${JSON.stringify(evidence)}`,
          strong: true,
          maxTokens: 2000,
          temperature: 0.3,
        });
        const people = await chatJson({
          system: scoreSys,
          user: `Score influence, teamwork, composure.\nCandidate ${userName}. Evidence: ${JSON.stringify(evidence)}`,
          strong: true,
          maxTokens: 2000,
          temperature: 0.3,
        });
        const found = {};
        for (const row of [...(content.competencies || []), ...(people.competencies || [])]) {
          if (row && row.id) found[row.id] = row;
        }
        const ids = [
          ["structure", "Structure"],
          ["commercial", "Commercial judgement"],
          ["insight", "Insight from materials"],
          ["influence", "Influence & presence"],
          ["teamwork", "Teamwork"],
          ["composure", "Composure under pressure"],
        ];
        const competencies = ids.map(([id, label]) => {
          const row = found[id] || {};
          let score = Number(row.score);
          if (!Number.isFinite(score)) score = 3;
          score = Math.max(1, Math.min(5, Math.round(score)));
          return { id, label: row.label || label, score, note: row.note || evidence.speaking_pattern || "" };
        });
        const wrap = await chatJson({
          system: "Write the final assessor debrief. JSON {headline, overall, verdict, what_worked, what_to_change, moments:[{quote,comment}], summary}.",
          user: `Candidate ${userName}. Case ${c.title}. Scores: ${JSON.stringify(competencies)}. Evidence: ${JSON.stringify(evidence)}`,
          strong: true,
          maxTokens: 2200,
          temperature: 0.35,
        });
        const avg = competencies.reduce((a, x) => a + x.score, 0) / competencies.length;
        this.session.debrief = {
          headline: wrap.headline || "Marked from the transcript",
          overall: Number(wrap.overall) || Math.round(avg * 10) / 10,
          verdict: wrap.verdict || "borderline",
          competencies,
          what_worked: wrap.what_worked || [],
          what_to_change: wrap.what_to_change || [],
          moments: wrap.moments || [],
          summary: wrap.summary || evidence.speaking_pattern || "",
        };
      } catch (e) {
        this.session.debrief = {
          headline: "Assessor could not finish",
          overall: 0,
          verdict: "",
          competencies: [],
          what_worked: [],
          what_to_change: [String(e.message || e)],
          moments: [],
          summary: String(e.message || e),
        };
      }
      this.send("debrief", { debrief: this.session.debrief });
    }

    async coach({ mode, question, highlight, notes }) {
      const c = this.session.case || {};
      const text = await chat({
        system: "You are a discreet Assessment Centre coach. Speak in second person. Concrete. 2–4 better moves plus an example sentence. Do not dump a model answer.",
        user: `Mode: ${mode}\nCase: ${c.title}\nAsk: ${c.discussion_ask}\nBrief: ${String(c.brief || "").slice(0, 1200)}\nNotes: ${notes || "(none)"}\nHighlight: ${highlight || "(none)"}\nQuestion: ${question || "(none)"}\nTranscript:\n${transcriptBlock(this.session.transcript || [], 40)}`,
        temperature: 0.5,
        maxTokens: 900,
      });
      return text;
    }

    packMarkdown() {
      const c = this.session.case || {};
      const notes = this.session.notes || "";
      const bits = [
        `# ${c.title || "Case pack"}`,
        "",
        `Client: ${c.client || ""}`,
        `Setting: ${c.setting || ""}`,
        `Timebox: ${c.timebox || ""}`,
        "",
        "## Objective",
        c.objective || "",
        "",
        "## The ask",
        c.discussion_ask || "",
        "",
        "Presentation: " + (c.presentation_ask || ""),
        "",
        "## Brief",
        c.brief || "",
        "",
        "## Constraints",
        ...(c.constraints || []).map((x) => `- ${x}`),
      ];
      (c.exhibits || []).forEach((e) => {
        bits.push("", `## ${e.name} (${e.kind})`, e.body || "");
      });
      if (notes) bits.push("", "## Your notes", notes);
      return bits.join("\n");
    }
  }

  global.BriefRoom = {
    MODELS,
    TTS_MODELS,
    settings,
    setSettings,
    Engine,
    catalog: () => global.BRIEF_CATALOG,
  };
})(window);
