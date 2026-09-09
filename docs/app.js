const state = {
  catalog: null,
  health: null,
  session: null,
  view: "setup",
  ws: null,
  engine: null,
  form: {
    industry_id: "consulting",
    difficulty: "standard",
    extra: "",
    user_name: "Alex",
    demo: true,
    panelists: [],
  },
  livePartial: "",
  speakingId: "",
  interrupted: false,
  coach: "",
  highlight: "",
  prepTab: "ask",
  packTab: "ask",
};

const $ = (id) => document.getElementById(id);
const views = {
  setup: $("view-setup"),
  prep: $("view-prep"),
  live: $("view-live"),
  debrief: $("view-debrief"),
};

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 3200);
}

function initials(name) {
  return (name || "?")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function fmt(secs) {
  const s = Math.max(0, Math.floor(secs));
  const m = Math.floor(s / 60);
  const r = String(s % 60).padStart(2, "0");
  return `${m}:${r}`;
}

function mdLite(text) {
  const esc = (s) =>
    s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  let html = esc(text || "");
  html = html.replace(/^### (.*)$/gm, "<h4>$1</h4>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\|(.+)\|/g, (row) => {
    const cells = row.split("|").filter(Boolean);
    if (cells.every((c) => /^[\s:-]+$/.test(c))) return "";
    return "<tr>" + cells.map((c) => `<td>${c.trim()}</td>`).join("") + "</tr>";
  });
  if (html.includes("<tr>")) html = html.replace(/(<tr>[\s\S]*<\/tr>)/, "<table>$1</table>");
  return html.replace(/\n/g, "<br>");
}

function packTabs(c) {
  const tabs = [
    { id: "ask", label: "The ask" },
    { id: "brief", label: "Brief" },
    { id: "constraints", label: "Constraints" },
  ];
  (c?.exhibits || []).forEach((e, i) => {
    tabs.push({ id: `ex-${i}`, label: e.name || `Exhibit ${i + 1}` });
  });
  tabs.push({ id: "notes", label: "Notes" });
  return tabs;
}

function packContent(tab, c, notes) {
  c = c || {};
  if (tab === "brief") return `<div class="case-body">${mdLite(c.brief || "No brief.")}</div>`;
  if (tab === "constraints") {
    const items = c.constraints || [];
    return items.length ? `<ul>${items.map((x) => `<li>${x}</li>`).join("")}</ul>` : "<p class='small'>None listed.</p>";
  }
  if (tab && tab.startsWith("ex-")) {
    const ex = (c.exhibits || [])[Number(tab.slice(3))];
    if (!ex) return "<p class='small'>Missing exhibit.</p>";
    return `<article class="exhibit"><h4>${ex.name} · ${ex.kind}</h4><div class="case-body">${mdLite(ex.body)}</div></article>`;
  }
  if (tab === "notes") return `<div class="case-body">${mdLite(notes || "No notes yet.")}</div>`;
  return `<p>${c.discussion_ask || ""}</p><p class="small">Presentation: ${c.presentation_ask || ""}</p>`;
}

function tabsHtml(active, c) {
  return `<div class="tabs">${packTabs(c).map(
    (t) => `<button type="button" data-tab="${t.id}" class="${t.id === active ? "active" : ""}">${t.label}</button>`
  ).join("")}</div>`;
}

function openPack(tab) {
  const s = state.session;
  if (!s) return;
  state.packTab = tab || state.packTab || "ask";
  const modal = $("pack-modal");
  modal.classList.remove("hidden");
  modal.innerHTML = `
    <div class="modal-sheet">
      <p class="kicker" id="pack-modal-title">Case pack</p>
      <h2>${(s.case && s.case.title) || "Pack"}</h2>
      ${tabsHtml(state.packTab, s.case)}
      <div class="scroll-pane pack-body">${packContent(state.packTab, s.case, s.notes)}</div>
      <div class="actions">
        <button class="btn ghost" type="button" id="pack-close">Close</button>
      </div>
    </div>`;
  modal.querySelectorAll("[data-tab]").forEach((b) => {
    b.onclick = () => openPack(b.dataset.tab);
  });
  $("pack-close").onclick = closePack;
  modal.onclick = (e) => {
    if (e.target === modal) closePack();
  };
}

function closePack() {
  const modal = $("pack-modal");
  modal.classList.add("hidden");
  modal.innerHTML = "";
}

function stages(n) {
  return `<div class="stages" aria-hidden="true">${[1, 2, 3, 4]
    .map((i) => `<span class="${i <= n ? "on" : ""}"></span>`)
    .join("")}</div>`;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail || detail;
    } catch (_) {}
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

function showView(name) {
  state.view = name;
  document.body.dataset.view = name;
  Object.entries(views).forEach(([k, el]) => el.classList.toggle("hidden", k !== name));
  renderTop();
}

function remainingNow() {
  const s = state.session;
  if (!s) return null;
  if (typeof s.remaining_seconds === "number") {
    const drift = (Date.now() - (s.clock_at || Date.now())) / 1000;
    return s.remaining_seconds - drift;
  }
  if (s.phase_ends_at) return s.phase_ends_at - Date.now() / 1000;
  return null;
}

function renderTop() {
  const s = state.session;
  const phase = s?.phase || "intake";
  const left = remainingNow();
  $("top-meta").innerHTML = `
    <dl class="dossier">
      <div><dt>Phase</dt><dd>${phase}</dd></div>
      <div><dt>Remaining</dt><dd class="timer" id="clock">${left == null ? "—" : fmt(left)}</dd></div>
      <div><dt>Track</dt><dd>${s?.industry?.name || "—"}</dd></div>
    </dl>
    <button class="gear" type="button" id="open-settings" title="Settings">Settings</button>
  `;
  if (!BriefRoom.settings.apiKey) {
    $("top-meta").insertAdjacentHTML(
      "beforeend",
      `<p class="small" style="margin:8px 0 0;max-width:24ch">No key this session · open Settings</p>`
    );
  }
  $("open-settings").onclick = openSettings;
}

function openSettings() {
  const modal = $("settings-modal");
  const models = BriefRoom.MODELS.map(
    (m) => `<option value="${m.id}" ${m.id === BriefRoom.settings.model ? "selected" : ""}>${m.label}</option>`
  ).join("");
  const strong = BriefRoom.MODELS.map(
    (m) => `<option value="${m.id}" ${m.id === BriefRoom.settings.modelStrong ? "selected" : ""}>${m.label}</option>`
  ).join("");
  const tts = BriefRoom.TTS_MODELS.map(
    (m) => `<option value="${m.id}" ${m.id === BriefRoom.settings.ttsModel ? "selected" : ""}>${m.label}</option>`
  ).join("");
  modal.classList.remove("hidden");
  modal.innerHTML = `
    <div class="modal-sheet">
      <p class="kicker">Session settings</p>
      <h2>API key and models</h2>
      <p class="small">Paste an OpenRouter key. It stays in this tab only — refresh clears it. Get a key at <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">openrouter.ai/keys</a>.</p>
      <label>OpenRouter API key
        <input id="set-key" type="password" autocomplete="off" placeholder="sk-or-v1-…" value="${BriefRoom.settings.apiKey ? "••••••••" : ""}" />
      </label>
      <label>Live model (panelists, interrupts, coach)
        <select id="set-model">${models}</select>
      </label>
      <label>Strong model (case pack + assessor)
        <select id="set-strong">${strong}</select>
      </label>
      <label>Voice
        <select id="set-tts">${tts}</select>
      </label>
      <div class="actions">
        <button class="btn ghost" type="button" id="set-cancel">Close</button>
        <button class="btn stamp-btn" type="button" id="set-save">Use this session</button>
      </div>
    </div>`;
  const save = () => {
    const typed = $("set-key").value.trim();
    const next = { model: $("set-model").value, modelStrong: $("set-strong").value, ttsModel: $("set-tts").value };
    if (typed && typed !== "••••••••") next.apiKey = typed;
    BriefRoom.setSettings(next);
    closeSettings();
    renderTop();
    toast(BriefRoom.settings.apiKey ? "Settings apply until you refresh." : "Still no key.");
  };
  $("set-save").onclick = save;
  $("set-cancel").onclick = closeSettings;
  modal.onclick = (e) => {
    if (e.target === modal) closeSettings();
  };
}

function closeSettings() {
  const modal = $("settings-modal");
  modal.classList.add("hidden");
  modal.innerHTML = "";
}

function tickClock() {
  const el = $("clock");
  if (!el) return;
  const left = remainingNow();
  if (left == null) return;
  el.textContent = fmt(left);
}

setInterval(tickClock, 500);

function personality(id) {
  return state.catalog?.personalities.find((p) => p.id === id);
}

function renderSetup() {
  const c = state.catalog;
  if (!c) {
    views.setup.innerHTML = `<p class="lede">Loading the candidate brief…</p>`;
    return;
  }
  if (!state.form.panelists.length) {
    state.form.panelists = c.default_panel.map((p) => ({ ...p }));
  }
  const industries = c.industries
    .map(
      (i, n) => `
      <button class="ticket stagger" style="animation-delay:${n * 40}ms" data-industry="${i.id}">
        <strong>${i.name}</strong>
        <span>${i.blurb}</span>
      </button>`
    )
    .join("");
  const panel = state.form.panelists
    .map((p, idx) => {
      const pers = personality(p.personality_id);
      return `
        <article class="sheet place-card">
          <span class="n">0${idx + 1}</span>
          <div class="person-head">
            <div class="avatar">${initials(p.name)}</div>
            <div>
              <strong>${p.name}</strong>
              <div class="small">${pers?.name || ""} — ${pers?.summary || ""}</div>
            </div>
          </div>
          <label>Name
            <input data-p="${idx}" data-k="name" value="${p.name}" />
          </label>
          <label>Personality
            <select data-p="${idx}" data-k="personality_id">
              ${c.personalities
                .map((x) => `<option value="${x.id}" ${x.id === p.personality_id ? "selected" : ""}>${x.name}</option>`)
                .join("")}
            </select>
          </label>
          <label>Accent
            <select data-p="${idx}" data-k="accent_id">
              ${c.accents
                .map((x) => `<option value="${x.id}" ${x.id === p.accent_id ? "selected" : ""}>${x.name}</option>`)
                .join("")}
            </select>
          </label>
          <label>Voice
            <select data-p="${idx}" data-k="voice_id">
              ${c.voices
                .map((x) => `<option value="${x.id}" ${x.id === p.voice_id ? "selected" : ""}>${x.name} — ${x.tone}</option>`)
                .join("")}
            </select>
          </label>
        </article>`;
    })
    .join("");

  views.setup.innerHTML = `
    <div class="hero">
      <div>
        <p class="kicker">Form 01 · Sit down</p>
        <h1>A table that talks back.</h1>
        <p class="lede">Ten minutes with the pack. Twenty with three other candidates who may cut you off. Then you present. An assessor has been marking the whole time.</p>
      </div>
      <p class="hero-index" aria-hidden="true">01</p>
    </div>
    ${stages(1)}
    ${
      !BriefRoom.settings.apiKey
        ? `<div class="alert" role="alert"><strong>No key this session.</strong> Open <button type="button" class="linkish" id="alert-settings">Settings</button>, paste an OpenRouter key, pick a model. Refreshing the page clears it.</div>`
        : ""
    }
    <article class="sheet">
      <h3>Industry track</h3>
      <div class="tickets stagger">${industries}</div>
      <div class="row" style="margin-top:18px">
        <label>Candidate name
          <input id="user_name" value="${state.form.user_name}" />
        </label>
        <label>Difficulty
          <select id="difficulty">
            <option value="easy" ${state.form.difficulty === "easy" ? "selected" : ""}>Easy</option>
            <option value="standard" ${state.form.difficulty === "standard" ? "selected" : ""}>Standard</option>
            <option value="hard" ${state.form.difficulty === "hard" ? "selected" : ""}>Hard</option>
          </select>
        </label>
      </div>
      <label style="margin-top:14px">Optional steer
        <input id="extra" placeholder="e.g. pricing a climate-tech roll-up" value="${state.form.extra}" />
      </label>
      <label class="check">
        <input type="checkbox" id="demo" ${state.form.demo ? "checked" : ""} />
        Demo clock (2 / 5 / 3 min). Uncheck for a full 10 / 20 / 8.
      </label>
    </article>
    <h3 style="margin-top:28px">The other three seats</h3>
    <p class="small">Personality, accent, and voice are independent. Randomise if you want a hostile table.</p>
    <div class="seats-config" style="margin-top:12px">${panel}</div>
    <div class="actions">
      <button class="btn ghost" id="randomise" type="button">Randomise the table</button>
      <button class="btn stamp-btn" id="start" type="button">Issue the pack</button>
    </div>
  `;

  views.setup.querySelectorAll("[data-industry]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.industry === state.form.industry_id);
    btn.onclick = () => {
      state.form.industry_id = btn.dataset.industry;
      renderSetup();
    };
  });
  views.setup.querySelectorAll("[data-p]").forEach((el) => {
    el.onchange = () => {
      const i = Number(el.dataset.p);
      state.form.panelists[i][el.dataset.k] = el.value;
    };
  });
  $("user_name").oninput = (e) => (state.form.user_name = e.target.value);
  $("difficulty").onchange = (e) => (state.form.difficulty = e.target.value);
  $("extra").oninput = (e) => (state.form.extra = e.target.value);
  $("demo").onchange = (e) => (state.form.demo = e.target.checked);
  $("randomise").onclick = randomisePanel;
  $("start").onclick = createSession;
  $("alert-settings")?.addEventListener("click", openSettings);
}

function randomisePanel() {
  const c = state.catalog;
  const names = ["Omar Haddad", "Sophie Laurent", "Daniel Okonkwo", "Aisha Rahman", "Kenji Sato", "Lucia Alvarez"];
  const used = new Set();
  state.form.panelists = [0, 1, 2].map((i) => {
    let name = names[Math.floor(Math.random() * names.length)];
    while (used.has(name)) name = names[(names.indexOf(name) + 1) % names.length];
    used.add(name);
    return {
      slot: i,
      name,
      personality_id: c.personalities[Math.floor(Math.random() * c.personalities.length)].id,
      accent_id: c.accents[Math.floor(Math.random() * c.accents.length)].id,
      voice_id: c.voices[i % c.voices.length].id,
    };
  });
  renderSetup();
}

async function createSession() {
  if (!BriefRoom.settings.apiKey) {
    openSettings();
    toast("Paste your OpenRouter key first.");
    return;
  }
  const btn = $("start");
  btn.disabled = true;
  btn.textContent = "Printing the pack…";
  try {
    ensureEngine();
    state.session = await state.engine.createSession({
      industry_id: state.form.industry_id,
      difficulty: state.form.difficulty,
      extra: state.form.extra,
      user_name: state.form.user_name,
      demo: state.form.demo,
      panelists: state.form.panelists,
    });
    showView("prep");
    renderPrep();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Issue the pack";
  }
}

function renderPrep() {
  const s = state.session;
  const c = s.case || {};
  views.prep.innerHTML = `
    <p class="kicker">Form 02 · Material study</p>
    <h1>${c.title || "Case pack"}</h1>
    <p class="lede">${c.client || ""} · ${c.industry_label || ""} · ${c.timebox || ""}</p>
    ${stages(2)}
    <div class="pack">
      <div class="folio">
        ${tabsHtml(state.prepTab, c)}
        <div class="scroll-pane pack-body" id="prep-pack">${packContent(state.prepTab, c, s.notes)}</div>
      </div>
      <aside class="margin-coach scroll">
        <h3>Margin notes</h3>
        <p class="small">Ask how to think, not for the answer. The assessor will notice a recitation.</p>
        <div class="actions">
          <button class="btn ghost" type="button" data-coach="prep_think">Generate points</button>
          <button class="btn ghost" type="button" data-coach="prep_organize">Organise this</button>
        </div>
        <label style="margin-top:12px">Your question
          <textarea id="prep-q" placeholder="How should I cut this pack?"></textarea>
        </label>
        <button class="btn" id="ask-prep" type="button">Ask the coach</button>
        <div class="coach-out" id="prep-out">${state.coach}</div>
        <label>Working notes
          <textarea id="notes">${s.notes || ""}</textarea>
        </label>
        <div class="actions">
          <button class="btn ghost" id="download-pack" type="button">Download pack</button>
          <button class="btn stamp-btn" id="go-live" type="button">Enter the table</button>
        </div>
      </aside>
    </div>
  `;
  views.prep.querySelectorAll("[data-tab]").forEach((b) => {
    b.onclick = () => {
      state.prepTab = b.dataset.tab;
      renderPrep();
    };
  });
  views.prep.querySelectorAll("[data-coach]").forEach((b) => {
    b.onclick = () => askCoach(b.dataset.coach, $("prep-q").value, "", "prep-out");
  });
  $("ask-prep").onclick = () => askCoach("prep_think", $("prep-q").value, "", "prep-out");
  $("notes").oninput = (e) => {
    s.notes = e.target.value;
    state.engine?.handle({ type: "notes", text: e.target.value });
  };
  $("download-pack").onclick = () => {
    const notes = $("notes")?.value || s.notes || "";
    if (state.engine) state.engine.session.notes = notes;
    const md = state.engine?.packMarkdown() || "";
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `briefroom-${(s.case?.title || "case-pack").toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 48)}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  };
  $("go-live").onclick = () => {
    state.session.phase = "discussion";
    showView("live");
    renderLive();
    state.engine?.handle({ type: "start_live" });
  };
}

function lastLine(id) {
  const t = [...(state.session?.transcript || [])].reverse().find((x) => x.speaker_id === id);
  return t ? t.text : "";
}

function plate(p) {
  const talking = state.speakingId === p.id;
  const hot = p.tag === "Competitive" || p.tag === "Loud";
  return `
    <article class="nameplate pos-${p.id} ${talking ? "talking" : ""}" data-seat="${p.id}">
      <div class="person-head">
        <div class="avatar">${initials(p.name)}</div>
        <div>
          <strong>${p.name}</strong>
          <div>
            <span class="tag ${hot ? "hot" : p.tag === "Kind" ? "kind" : ""}">${p.tag || p.personality_name || "Candidate"}</span>
            <span class="tag">${p.accent_name || ""}</span>
          </div>
        </div>
      </div>
    </article>`;
}

function renderLive() {
  const s = state.session;
  const phase = s.phase === "presentation" ? "presentation" : "discussion";
  const balloons = (s.panelists || [])
    .map((p) => {
      const talking = state.speakingId === p.id;
      const cut = state.interrupted && talking;
      return `
        <div class="balloon ${talking ? "talking" : ""} ${cut ? "interrupt" : ""}">
          <span class="who">${p.name}${cut ? " · cut in" : talking ? " · speaking" : ""}</span>
          <p>${lastLine(p.id) || "Waiting."}</p>
        </div>`;
    })
    .join("");
  const seats = (s.panelists || []).map(plate).join("");
  const youLast = lastLine("user");
  const log = (s.transcript || [])
    .map(
      (t) => `
      <div class="line ${t.speaker_id === "user" ? "user" : ""} ${t.interrupt ? "cut" : ""}">
        <span class="who">${t.speaker_name}${t.interrupt ? " · cut in" : ""} · ${t.phase}</span>
        ${t.text}
      </div>`
    )
    .join("");

  views.live.innerHTML = `
    <p class="kicker">Form 0${phase === "discussion" ? "3" : "4"} · ${phase}</p>
    <h1>${phase === "discussion" ? "Hold the floor." : "Present."}</h1>
    <p class="lede">${
      phase === "presentation"
        ? (s.case?.presentation_ask || "Pitch the recommendation as a group.") + " Agents go around: one point each, many times. No interruptions. Hold Space if you want a point."
        : (s.case?.discussion_ask || "") + " Near the end they will wrap and set a speaking order."
    }</p>
    ${stages(3)}
    <div class="tabs">
      ${packTabs(s.case).map((t) => `<button type="button" data-pack="${t.id}">${t.label}</button>`).join("")}
    </div>
    <div class="table-wrap">
      <div class="speech-rail">${balloons}</div>
      <div class="table">${seats}</div>
      <div class="you-row">
        <article class="you-card ${state.speakingId === "user" ? "talking" : ""}">
          <div class="person-head">
            <div class="avatar">${initials(s.user_name || "You")}</div>
            <div>
              <strong>${s.user_name || "You"}</strong>
              <div><span class="tag">You</span></div>
            </div>
          </div>
          <p class="caption">${youLast || state.livePartial || "Your line."}</p>
        </article>
        <div class="mic-beside">
          <button class="mic" id="mic" type="button" aria-label="Push to talk">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 3a3 3 0 0 1 3 3v6a3 3 0 1 1-6 0V6a3 3 0 0 1 3-3Z" stroke="currentColor" stroke-width="1.7"/>
              <path d="M6 11a6 6 0 0 0 12 0M12 17v4M8 21h8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
            </svg>
          </button>
          <div>
            <strong id="mic-label">Hold Space</strong>
            <div class="partial" id="partial">${state.livePartial || (phase === "presentation" ? "Your pitch. No one will cut in." : "They may cut in.")}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="live-bar">
      <p class="small">${
        phase === "presentation"
          ? "Round-robin. Each agent, one point, then they pass the mic. You may add a point anytime."
          : "Mic is beside you. Pack tabs open a popup."
      }</p>
      <button class="btn ghost" id="advance" type="button">${phase === "discussion" ? "Start presentation" : "Sit for debrief"}</button>
    </div>
    <article class="sheet" style="margin-top:16px">
      <h3>Minutes</h3>
      <div class="log">${log || "<p class='small'>The table is quiet.</p>"}</div>
    </article>
  `;
  $("mic").onpointerdown = () => startTalk();
  $("mic").onpointerup = () => stopTalk();
  $("mic").onpointercancel = () => stopTalk();
  $("mic").onpointerleave = (e) => {
    if (e.buttons) stopTalk();
  };
  $("advance").onclick = () => state.engine?.handle({ type: "advance" });
  views.live.querySelectorAll("[data-pack]").forEach((b) => {
    b.onclick = () => openPack(b.dataset.pack);
  });
}

function renderDebrief() {
  const s = state.session;
  const d = s.debrief || {};
  const comps = (d.competencies || [])
    .map(
      (c) => `
      <div class="score-row">
        <span style="width:180px">${c.label}</span>
        <div class="bar"><span style="width:${(c.score / 5) * 100}%"></span></div>
        <strong>${c.score}/5</strong>
      </div>
      <p class="small">${c.note || ""}</p>`
    )
    .join("");
  const log = (s.transcript || [])
    .map(
      (t) => `
      <div class="line transcript-select ${t.speaker_id === "user" ? "user" : ""} ${t.interrupt ? "cut" : ""}">
        <span class="who">${t.speaker_name}${t.interrupt ? " · cut in" : ""}</span>
        ${t.text}
      </div>`
    )
    .join("");
  views.debrief.innerHTML = `
    <p class="kicker">Form 05 · Assessor marks</p>
    <h1 class="full-bleed">${d.headline || "Marked script"}</h1>
    <p class="lede full-bleed">${d.summary || "The assessor is still writing in the margin."}</p>
    ${stages(4)}
    <div class="tabs">
      ${packTabs(s.case).map((t) => `<button type="button" data-pack="${t.id}">${t.label}</button>`).join("")}
    </div>
    <div class="pack">
      <article class="folio scroll">
        <h3>Overall ${d.overall ? Number(d.overall).toFixed(1) : "—"} · ${d.verdict || ""}</h3>
        ${comps}
        <h3 style="margin-top:22px">What held</h3>
        <ul>${(d.what_worked || []).map((x) => `<li>${x}</li>`).join("")}</ul>
        <h3>Change in red</h3>
        <ul>${(d.what_to_change || []).map((x) => `<li>${x}</li>`).join("")}</ul>
      </article>
      <aside class="margin-coach scroll">
        <h3>Replay</h3>
        <p class="small">Highlight a line in the minutes, or type a question, then ask the coach.</p>
        <label>Highlighted span
          <textarea id="hl">${state.highlight}</textarea>
        </label>
        <label>Question
          <textarea id="debrief-q" placeholder="How should I have responded?"></textarea>
        </label>
        <div class="actions">
          <button class="btn stamp-btn" type="button" id="ask-debrief">Ask the coach</button>
          <button class="btn ghost" type="button" data-coach="better_line">Better line</button>
          <button class="btn ghost" type="button" data-coach="situation">How to think here</button>
        </div>
        <div class="coach-out" id="debrief-out">${state.coach}</div>
      </aside>
    </div>
    <article class="sheet" style="margin-top:16px">
      <h3>Full minutes</h3>
      <div class="log" id="full-log">${log}</div>
    </article>
  `;
  $("full-log")?.addEventListener("mouseup", () => {
    const sel = window.getSelection()?.toString().trim();
    if (sel) {
      state.highlight = sel;
      $("hl").value = sel;
    }
  });
  views.debrief.querySelectorAll("[data-pack]").forEach((b) => {
    b.onclick = () => openPack(b.dataset.pack);
  });
  $("ask-debrief").onclick = () =>
    askCoach("better_line", $("debrief-q").value, $("hl").value, "debrief-out");
  views.debrief.querySelectorAll("[data-coach]").forEach((b) => {
    b.onclick = () => askCoach(b.dataset.coach, $("debrief-q").value, $("hl").value, "debrief-out");
  });
}

async function askCoach(mode, question, highlight, outId) {
  const el = document.getElementById(outId);
  if (el) el.textContent = "In the margin…";
  try {
    const answer = await state.engine.coach({
      mode,
      question,
      highlight,
      notes: state.session.notes || "",
    });
    state.coach = answer;
    if (el) el.textContent = answer;
  } catch (err) {
    toast(err.message);
  }
}

function ensureEngine() {
  if (state.engine) return;
  state.engine = new BriefRoom.Engine((msg) => onEngine(msg));
}

function onEngine(msg) {
  if (msg.session) state.session = msg.session;
  if (msg.type === "clock") {
    if (!state.session) state.session = {};
    state.session.remaining_seconds = msg.remaining;
    state.session.clock_at = Date.now();
    state.session.phase_ends_at = Date.now() / 1000 + msg.remaining;
    tickClock();
  }
  if (msg.type === "phase") {
    state.session.phase = msg.phase;
    state.session.phase_ends_at = msg.phase_ends_at;
    if (msg.remaining != null) {
      state.session.remaining_seconds = msg.remaining;
      state.session.clock_at = Date.now();
    }
    renderTop();
    if (msg.phase === "debrief") {
      showView("debrief");
      renderDebrief();
    } else {
      showView("live");
      renderLive();
    }
  }
  if (msg.type === "turn") {
    state.session.transcript = state.session.transcript || [];
    if (!state.session.transcript.some((t) => t.id === msg.turn?.id)) {
      state.session.transcript.push(msg.turn);
    }
    state.speakingId = msg.turn.speaker_id;
    state.interrupted = !!msg.interrupt;
    if (msg.speech_gen != null) state.speechGen = msg.speech_gen;
    if (msg.interrupt) stopTalk(true);
    if (msg.turn?.speaker_id !== "user") {
      if (msg.audio_b64) playAudio(msg.audio_b64, msg.speech_gen);
      else speakLocal(msg.turn?.text || "", msg.accent_id, msg.speech_gen);
    } else {
      signalSpoken(msg.speech_gen);
    }
    if (state.view === "live") renderLive();
  }
  if (msg.type === "barge_in") {
    state.interrupted = true;
    stopTalk(true);
    killAudio();
    signalSpoken(state.speechGen);
    toast("Someone cut in");
  }
  if (msg.type === "debrief") {
    state.session.debrief = msg.debrief;
    showView("debrief");
    renderDebrief();
  }
  if (msg.type === "status") toast(msg.message);
  if (msg.type === "error") toast(msg.message);
  renderTop();
}

let audioCtx;
let rec = null;
let recStream = null;
let recognition = null;
let chunks = [];
let talking = false;

function ensureAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
}

function signalSpoken(gen) {
  state.engine?.handle({ type: "speech_done", speech_gen: gen ?? state.speechGen });
}

function armSpoken(gen, ms) {
  let sent = false;
  const done = () => {
    if (sent) return;
    sent = true;
    if (state._spokenTimer) {
      clearTimeout(state._spokenTimer);
      state._spokenTimer = null;
    }
    signalSpoken(gen);
  };
  state._spokenTimer = setTimeout(done, Math.max(800, ms || 4000));
  return done;
}

async function playAudio(b64, gen) {
  killAudio();
  ensureAudio();
  try {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const buf = await audioCtx.decodeAudioData(bin.buffer.slice(0));
    const src = audioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(audioCtx.destination);
    const done = armSpoken(gen, (buf.duration || 1) * 1000 + 400);
    src.onended = done;
    src.start();
    state._src = src;
  } catch (_) {
    speakLocal(state.session?.transcript?.slice(-1)[0]?.text || "", "american", gen);
  }
}

function speakLocal(text, accentId, gen) {
  if (!text) {
    signalSpoken(gen);
    return;
  }
  if (!window.speechSynthesis) {
    signalSpoken(gen);
    return;
  }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const lang = {
    british: "en-GB",
    indian: "en-IN",
    australian: "en-AU",
    irish: "en-IE",
    singaporean: "en-SG",
    south_african: "en-ZA",
    american: "en-US",
  }[accentId] || "en-US";
  u.lang = lang;
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(lang.toLowerCase()));
  if (match) u.voice = match;
  const done = armSpoken(gen, Math.min(18000, 900 + text.split(/\s+/).length * 420));
  u.onend = done;
  u.onerror = done;
  window.speechSynthesis.speak(u);
}

if (window.speechSynthesis) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

function killAudio() {
  if (state._spokenTimer) {
    clearTimeout(state._spokenTimer);
    state._spokenTimer = null;
  }
  try {
    state._src?.stop();
  } catch (_) {}
  state._src = null;
  try {
    window.speechSynthesis?.cancel();
  } catch (_) {}
}

function startTalk() {
  if (talking) return;
  talking = true;
  ensureAudio();
  killAudio();
  state.interrupted = false;
  $("mic")?.classList.add("live");
  if (document.getElementById("mic-label")) document.getElementById("mic-label").textContent = "Listening";
  state.engine?.handle({ type: "start_speaking" });
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (e) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += t;
        else interim += t;
      }
      const live = (final + " " + interim).trim();
      state.livePartial = live;
      const p = document.getElementById("partial");
      if (p) p.textContent = live;
      state.engine?.handle({ type: "partial", text: live });
    };
    recognition.start();
    return;
  }
  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    recStream = stream;
    rec = new MediaRecorder(stream);
    chunks = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.start();
  });
}

async function stopTalk(fromInterrupt = false) {
  if (!talking && !fromInterrupt) return;
  talking = false;
  $("mic")?.classList.remove("live");
  if (document.getElementById("mic-label")) document.getElementById("mic-label").textContent = "Hold Space";
  if (recognition) {
    try {
      recognition.stop();
    } catch (_) {}
    recognition = null;
  }
  let finalText = state.livePartial;
  if (rec && rec.state !== "inactive") {
    await new Promise((resolve) => {
      rec.onstop = resolve;
      rec.stop();
    });
    recStream?.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
    const fd = new FormData();
    fd.append("file", blob, "clip.webm");
    try {
      /* no server STT on github.io — Chrome speech already filled livePartial */
    } catch (_) {}
  }
  state.engine?.handle({ type: fromInterrupt ? "stop_speaking" : "final", text: finalText });
  state.livePartial = "";
}

window.addEventListener("keydown", (e) => {
  if (e.code === "Escape") {
    closePack();
    closeSettings();
  }
  if (e.code === "Space" && state.view === "live") {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    e.preventDefault();
    if (!e.repeat) startTalk();
  }
});
window.addEventListener("keyup", (e) => {
  if (e.code === "Space" && state.view === "live") {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    stopTalk();
  }
});

async function boot() {
  state.catalog = window.BRIEF_CATALOG;
  state.health = { has_key: !!BriefRoom.settings.apiKey, provider: "openrouter" };
  renderSetup();
  renderTop();
  openSettings();
}

boot();
