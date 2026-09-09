const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, VerticalAlign, PageNumber,
  TableOfContents, TabStopType, TabStopPosition,
} = require("docx");
const fs = require("fs");
const path = require("path");

const PAGE_W = 11906; // A4
const PAGE_H = 16838;
const MARGIN = 1134; // 0.79"
const CONTENT_W = PAGE_W - MARGIN * 2; // 9638

const INK = "1C1917";
const MUTED = "57534E";
const ACCENT = "7C2D12";
const RULE = "C4B5A5";
const CREAM = "F5EDE3";
const HEADER_FILL = "3F2A1D";
const ALT = "FAF6F1";
const PROMPT_BG = "F3EEE6";
const WHITE = "FFFFFF";

const thin = { style: BorderStyle.SINGLE, size: 4, color: RULE };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function run(text, opts = {}) {
  return new TextRun({
    text,
    font: opts.mono ? "Consolas" : (opts.font || "Arial"),
    size: opts.size || 22,
    bold: !!opts.bold,
    italics: !!opts.italics,
    color: opts.color || INK,
  });
}

function para(children, extra = {}) {
  return new Paragraph({
    spacing: { after: extra.after ?? 160, before: extra.before ?? 0, line: extra.line || 276 },
    alignment: extra.align,
    border: extra.border,
    numbering: extra.numbering,
    heading: extra.heading,
    keepNext: extra.keepNext,
    children: Array.isArray(children) ? children : [run(children, extra.run || {})],
  });
}

function body(text) {
  return para(text, { after: 180 });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 4 } },
    children: [new TextRun({ text, font: "Arial", size: 32, bold: true, color: INK })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, font: "Arial", size: 26, bold: true, color: ACCENT })],
  });
}

function bullet(text, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 80, line: 276 },
    children: [new TextRun({ text, font: "Arial", size: 22, color: INK })],
  });
}

function caption(text) {
  return para([run(text, { size: 18, italics: true, color: MUTED })], { after: 200, before: 40 });
}

function cell(text, width, opts = {}) {
  const isHeader = !!opts.header;
  const lines = Array.isArray(text) ? text : [text];
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: isHeader ? HEADER_FILL : (opts.fill || WHITE), type: ShadingType.CLEAR },
    margins: { top: 70, bottom: 70, left: 100, right: 100 },
    verticalAlign: VerticalAlign.TOP,
    children: lines.map((line, i) =>
      new Paragraph({
        spacing: { after: i === lines.length - 1 ? 0 : 40 },
        children: [
          new TextRun({
            text: line,
            font: opts.mono ? "Consolas" : "Arial",
            size: isHeader ? 18 : (opts.size || 20),
            bold: isHeader || !!opts.bold,
            color: isHeader ? WHITE : INK,
            italics: !!opts.italics,
          }),
        ],
      })
    ),
  });
}

function table(colWidths, rows) {
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: rows.map((row, i) => new TableRow({ tableHeader: i === 0, children: row })),
  });
}

function spacer(after = 200) {
  return new Paragraph({ spacing: { after }, children: [] });
}

function promptBlock(title, lines) {
  return [
    new Paragraph({
      spacing: { before: 120, after: 60 },
      keepNext: true,
      children: [new TextRun({ text: title, font: "Arial", size: 20, bold: true, color: ACCENT })],
    }),
    new Table({
      width: { size: CONTENT_W, type: WidthType.DXA },
      columnWidths: [CONTENT_W],
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            new TableCell({
              borders: {
                top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
                bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
                left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT },
                right: { style: BorderStyle.SINGLE, size: 4, color: RULE },
              },
              width: { size: CONTENT_W, type: WidthType.DXA },
              shading: { fill: PROMPT_BG, type: ShadingType.CLEAR },
              margins: { top: 120, bottom: 120, left: 160, right: 140 },
              children: lines.map(
                (line) =>
                  new Paragraph({
                    spacing: { after: 40, line: 260 },
                    children: [
                      new TextRun({
                        text: line === "" ? " " : line,
                        font: "Consolas",
                        size: 18,
                        color: INK,
                      }),
                    ],
                  })
              ),
            }),
          ],
        }),
      ],
    }),
    spacer(140),
  ];
}

const W2A = Math.round(CONTENT_W * 0.38);
const W2B = CONTENT_W - W2A;
const W3A = 2200;
const W3B = 3720;
const W3C = CONTENT_W - W3A - W3B;
const W4 = [1800, 2400, 2400, CONTENT_W - 1800 - 2400 - 2400];

const children = [
  new Paragraph({
    spacing: { after: 40 },
    children: [new TextRun({ text: "DEMONSTRATION WRITE-UP", font: "Arial", size: 18, bold: true, color: ACCENT })],
  }),
  new Paragraph({
    spacing: { after: 80, line: 276 },
    children: [new TextRun({ text: "BriefRoom", font: "Arial", size: 56, bold: true, color: INK })],
  }),
  new Paragraph({
    spacing: { after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 8 } },
    children: [
      new TextRun({
        text: "An AI-powered Assessment Centre rehearsal",
        font: "Arial",
        size: 26,
        italics: true,
        color: MUTED,
      }),
    ],
  }),
  para(
    [
      run("A journey covering what was built, how it works, how AI was used, and what changed in the build.", {
        size: 22,
        color: INK,
      }),
    ],
    { after: 80 }
  ),
  para(
    [
      run("Product  ", { bold: true, size: 20, color: MUTED }),
      run("BriefRoom  ·  ", { size: 20 }),
      run("Stack  ", { bold: true, size: 20, color: MUTED }),
      run("LangGraph + FastAPI + OpenRouter  ·  ", { size: 20 }),
      run("Date  ", { bold: true, size: 20, color: MUTED }),
      run("August 2026", { size: 20 }),
    ],
    { after: 280 }
  ),

  new Paragraph({
    spacing: { before: 80, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 4 } },
    children: [new TextRun({ text: "Contents", font: "Arial", size: 32, bold: true, color: INK })],
  }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  spacer(200),

  h1("1.  Problem statement"),
  body(
    "Graduate and professional hiring still uses Assessment Centres: a timed case pack, a group discussion with strangers, a presentation, and an assessor who scores presence, structure, and teamwork. The thing that actually fails people is not the written case. It is the live table."
  ),
  body("You cannot rehearse that table with the tools most candidates have."),
  bullet("Mock interviews are one-to-one. Real Assessment Centres are multi-party, with people who talk over you."),
  bullet("Reading case books does not train holding the floor when someone rude cuts in."),
  bullet("Feedback arrives days later, if at all, and never as a transcript you can interrogate."),
  bullet("Coaches are expensive. University careers services cannot sit six times a week at a live table."),
  spacer(80),
  body(
    "The opportunity is a rehearsal room that feels like the real table: mixed personalities, mixed accents, live voice, rational interruption, then a specific debrief. That is the real-world challenge BriefRoom addresses."
  ),

  h1("2.  What was built"),
  body(
    "BriefRoom is a browser Assessment Centre. The candidate sits at a cream institutional desk with three AI peers, studies a generated pack, speaks on a microphone, gets interrupted in character, presents as a team, and leaves with a scored debrief plus a coach that can rewrite any highlighted line."
  ),
  para("The live flow is:", { after: 80 }),
  bullet("Setup. Pick an industry (consulting, investment banking, product, healthcare, FMCG, policy, energy, media). Configure three other candidates: personality, accent, and voice."),
  bullet("Prep (10 minutes, or 2 in demo). The model writes a full pack: client, exhibits, constraints, discussion ask, presentation ask. A coach on the side teaches how to generate points and how to organise them. It will not dump a model answer. A Download pack PDF button exports the candidate-facing materials."),
  bullet("Group discussion (20 minutes, or 5 in demo). The candidate speaks on the microphone. Three concurrent panelists listen to live partial transcripts. Some are kind facilitators. Some interrupt, but only if it is in-character and the content justifies it."),
  bullet("Group presentation. The same table presents a recommendation. No interrupts. One point per turn, many laps, every AI seat speaks, the candidate has a reserved slot."),
  bullet("Assessor debrief. A separate LLM, with a hidden rubric from case generation, scores six competencies and quotes the candidate."),
  bullet("Replay coach. Highlight any line in the transcript and ask how to have responded, or how to think in that situation."),
  spacer(80),
  body(
    "The first version ships three panelists. The data model already supports six. Sessions live in memory for the demo; no login is required."
  ),

  h1("3.  Solution overview \u2014 how it works"),
  h2("3.1  Architecture"),
  body(
    "LangGraph, not a single chain. The Assessment Centre is a state machine with concurrent agents. A FastAPI WebSocket room is the conductor: timers, floor, who speaks next, audio playback. It calls named graph nodes. It does not pretend to be the model."
  ),
  table([W2A, W2B], [
    [cell("Layer", W2A, { header: true }), cell("Choice", W2B, { header: true })],
    [cell("App / conductor", W2A, { fill: ALT }), cell("FastAPI WebSocket room \u2014 floor, barge-in, official clock", W2B, { fill: ALT })],
    [cell("Orchestration", W2A), cell("LangGraph compiled subgraphs, invoked from the room", W2B)],
    [cell("Live reasoning", W2A, { fill: ALT }), cell("OpenRouter chat completions (OpenAI-compatible, not Responses API)", W2B, { fill: ALT })],
    [cell("Voice out", W2A), cell("OpenRouter POST /audio/speech, then browser speechSynthesis fallback", W2B)],
    [cell("Voice in", W2A, { fill: ALT }), cell("Chrome Web Speech API for live partials; OpenRouter STT as fallback", W2B, { fill: ALT })],
    [cell("Frontend", W2A), cell("Static HTML / CSS / JS. Institutional print: cream paper, Big Shoulders Display, Literata, Barlow Condensed", W2B)],
    [cell("Pack export", W2A, { fill: ALT }), cell("ReportLab PDF at GET /api/sessions/{id}/pdf \u2014 no hidden rubric", W2B, { fill: ALT })],
  ]),
  caption("Table 1. Stack as shipped."),
  spacer(40),

  h2("3.2  LangGraph nodes"),
  table([W2A, W2B], [
    [cell("Node", W2A, { header: true }), cell("Job", W2B, { header: true })],
    [cell("generate_case", W2A, { fill: ALT, mono: true }), cell("Writes the candidate pack plus a hidden assessor rubric", W2B, { fill: ALT })],
    [cell("interrupt_vote", W2A, { mono: true }), cell("One panelist decides whether to barge in on the live partial", W2B)],
    [cell("pick_interrupt", W2A, { fill: ALT, mono: true }), cell("Highest urgency that also passes a personality dice roll", W2B, { fill: ALT })],
    [cell("panelist_speech", W2A, { mono: true }), cell("In-character spoken turn, generated once then played through", W2B)],
    [cell("write_debrief", W2A, { fill: ALT, mono: true }), cell("Competency scores from the full transcript", W2B, { fill: ALT })],
    [cell("coach_reply", W2A, { mono: true }), cell("Prep thinking / organisation / better line / situation", W2B)],
  ]),
  caption("Table 2. Named jobs in the graph."),
  spacer(40),

  h2("3.3  Two floors, not one policy"),
  body(
    "Discussion and presentation are different social games. They do not share an interrupt policy."
  ),
  bullet("Discussion floor. Interrupts are allowed. While anyone is talking, run_interrupt_jury fans out one interrupt_vote per other panelist with asyncio.gather. Every bot reads the same incomplete sentence. A personality prior (rude seats around 0.62, facilitators around 0.08) then allows a cut-in. The interruption line has to be about what is being said now."),
  bullet("Presentation floor. No interrupts. Round-robin, one point per turn, many laps. All AI agents speak. If the candidate skips their slot, another LLM covers that slice. The wrap of discussion produces a speak_order and coverage slices; the presentation follows that plan."),
  spacer(80),
  body(
    "Frozen scripts: a panelist generates once, then the audio plays through. An interrupt stops playback and triggers a new script. Agent-on-agent barge-in is watched so the table does not collapse into overlapping speech."
  ),

  h2("3.4  Clock, wrap, and speaking order"),
  body(
    "The official clock is server remaining time: phase duration minus elapsed. It is injected into prompts. The model is not allowed to guess when time is up. Wrap is permitted only in the last 30 seconds, and only when the director note says WRAP THE DISCUSSION. A wrap produces the presentation speak order."
  ),
  body(
    "If the candidate stays quiet in discussion, a weighted picker (talkativeness, recency, phase) gives someone else the floor. After two AI turns the room waits longer for the candidate. That is randomised order with a bias, not a round-robin that no real Assessment Centre uses."
  ),

  h2("3.5  Voice path"),
  body(
    "Panelist audio is OpenRouter TTS (hexgrad/Kokoro as the pinned default) with distinct voices plus an accent instruction in the prompt. Speed is omitted except for providers that accept it. Last-good TTS is remembered so a 502 does not keep retrying a dead model. The browser speechSynthesis API is the local fallback."
  ),
  body(
    "The candidate microphone uses the Web Speech API for low-latency partials so interruption can happen before the sentence finishes. Completed clips can go to OpenRouter STT when Chrome speech recognition is missing."
  ),
  body("No API key is ever sent to the browser. TTS and STT are proxied."),

  h1("4.  Use of AI"),
  h2("4.1  AI coding tools used"),
  body(
    "Grok Build (this session) designed the architecture, wrote the LangGraph graph, FastAPI room, voice wiring, and the frontend. A user-scoped frontend-design skill was added mid-build to kill generic dark-dashboard UI: cream institutional print, no emoji-as-icons, 44px microphone target, cache-busted static assets."
  ),
  body(
    "The coding agent was also the debugger: OpenRouter geo-403s, invalid model slugs, TTS 400/502s, wrap-too-early, and the discussion/presentation interrupt collision were all found in live runs and patched in the same loop."
  ),

  h2("4.2  Models, APIs, and platforms"),
  table([W3A, W3B, W3C], [
    [cell("Role", W3A, { header: true }), cell("Model / API", W3B, { header: true }), cell("Why", W3C, { header: true })],
    [
      cell("Live panelists, interrupt jury, coach", W3A, { fill: ALT }),
      cell("OpenRouter deepseek/deepseek-v4-flash via https://openrouter.ai/api/v1 chat completions", W3B, { fill: ALT }),
      cell("Latency. Three concurrent votes cannot wait on a slow model.", W3C, { fill: ALT }),
    ],
    [
      cell("Case writer + assessor", W3A),
      cell("OpenRouter deepseek/deepseek-v4-pro (OPENROUTER_MODEL_STRONG)", W3B),
      cell("Harder reasoning, hidden rubric, fairer scores.", W3C),
    ],
    [
      cell("Fallbacks if 400 / 403 / 404 / 429", W3A, { fill: ALT }),
      cell("DeepSeek chat, Qwen, Llama 3.3, Mistral", W3B, { fill: ALT }),
      cell("OpenAI and Gemini slugs were geo-blocked or invalid in this region.", W3C, { fill: ALT }),
    ],
    [
      cell("Panelist voices", W3A),
      cell("OpenRouter TTS POST /audio/speech \u2014 hexgrad/kokoro-82m", W3B),
      cell("Distinct voices plus accent instructions. Last-good model is cached.", W3C),
    ],
    [
      cell("Accurate fallback transcription", W3A, { fill: ALT }),
      cell("OpenRouter STT mistralai/voxtral-mini-3b-2507, then openai/whisper-1", W3B, { fill: ALT }),
      cell("When Chrome speech recognition is missing.", W3C, { fill: ALT }),
    ],
    [
      cell("Orchestration", W3A),
      cell("LangGraph", W3B),
      cell("Phase machine plus concurrent agents as named nodes.", W3C),
    ],
    [
      cell("App", W3A, { fill: ALT }),
      cell("FastAPI WebSocket room", W3B, { fill: ALT }),
      cell("Floor, barge-in, timers. Graph nodes are workers, not the conductor.", W3C, { fill: ALT }),
    ],
  ]),
  caption("Table 3. Models and APIs in the product. Keys stay on the server."),
  spacer(40),
  body(
    "LangGraph was chosen over LangChain chains because the Assessment Centre is not one chatbot. It is phases, concurrent votes, and separate roles (case writer, speaker, interrupt jury, assessor, coach) that the live room must invoke independently."
  ),

  h2("4.3  System prompts (examples)"),
  body(
    "Each role has its own system prompt. The room injects remaining time, phase, live partials, and a director note. Below are shortened excerpts from the shipped prompts."
  ),

  ...promptBlock("Case writer \u2014 pack the candidate sees, rubric they do not", [
    "You are a senior Assessment Centre designer for graduate and early-career hiring.",
    "You write realistic group-exercise packs that a real firm would put on the table.",
    "",
    "Rules:",
    "- Invent a specific company, numbers, and trade-offs. No generic \"Company X\".",
    "- The pack must be readable in 8\u201310 minutes.",
    "- Include at least one uncomfortable trade-off (ethics, politics, short vs long term).",
    "- Do not include a model answer in the candidate-facing materials.",
    "- The hidden rubric is for assessors only.",
  ]),

  ...promptBlock("Panelist \u2014 identity, dialect, interrupt vs present", [
    "You are {name}, a real candidate in a live Assessment Centre group exercise.",
    "You are NOT an interviewer and you are NOT an AI. Never break character.",
    "",
    "Identity:",
    "- Personality: {personality_name} ({tag})",
    "- How you behave: {style}",
    "- Spoken dialect: {dialect}",
    "",
    "If you are interrupting:",
    "- Sentence 1 MUST react to the live, unfinished words.",
    "- Only then add your own point.",
    "",
    "If you are presenting:",
    "- TEAM presentation. No interrupts. ONE point per turn.",
    "- You will get the mic again later. Do not dump a whole speech.",
    "",
    "Do not wrap up unless the director note says WRAP THE DISCUSSION.",
    "A few minutes left is NOT wrap time. Wrap only in the last 30 seconds.",
  ]),

  ...promptBlock("Interrupt jury \u2014 every live panelist, in parallel", [
    "You are deciding whether {name} would interrupt the person who is still talking.",
    "Interruptions are rare. Default to false.",
    "Only interrupt if ALL are true:",
    "- they have said enough that you can quote a claim (not the first 18 words)",
    "- you strongly disagree or they are wrong vs the pack",
    "- your first sentence can name that claim",
    "",
    "Return JSON: { interrupt, urgency, reason, line }",
  ]),
  body(
    "The room then applies interrupt_p as a prior so a kind facilitator almost never fires even if the model is tempted."
  ),

  ...promptBlock("Assessor \u2014 separate model, transcript-only evidence", [
    "You are the lead assessor at a professional Assessment Centre.",
    "Score only what is evidenced in the transcript. Quote them. Be kind but not fluffy.",
    "Name what to do differently next time in behavioural language.",
    "",
    "Competencies: Structure, Commercial judgement, Influence & presence,",
    "Teamwork, Composure under pressure, Insight from materials.",
  ]),

  ...promptBlock("Coach \u2014 prep and highlighted transcript spans", [
    "You are a discreet Assessment Centre coach sitting just off-camera.",
    "Offer 2\u20134 better moves, including an example sentence they could have said.",
    "If they ask about prep, teach how to extract issues, structure, and a point of view",
    "\u2014 do not dump a model answer that removes the exercise.",
    "",
    "Modes: prep_think | prep_organize | better_line | situation",
  ]),

  h1("5.  Impact and value"),
  table([W2A, W2B], [
    [cell("Without BriefRoom", W2A, { header: true }), cell("With BriefRoom", W2B, { header: true })],
    [cell("One friend playing \u201Cbad cop\u201D", W2A, { fill: ALT }), cell("Three calibrated personalities, on demand", W2B, { fill: ALT })],
    [cell("No record of what you said", W2A), cell("Full transcript, including who interrupted", W2B)],
    [cell("Vague \u201Cspeak up more\u201D", W2A, { fill: ALT }), cell("Competency scores with quotes", W2B, { fill: ALT })],
    [cell("Cannot practise interruption", W2A), cell("Live barge-in while you are still talking", W2B)],
    [cell("Case books recycle", W2A, { fill: ALT }), cell("A new pack per industry, every run, plus a printable PDF", W2B, { fill: ALT })],
    [cell("Presentation is an afterthought", W2A), cell("A second workflow: ordered one-point rotation, no interrupts", W2B)],
  ]),
  caption("Table 4. What changes for the candidate."),
  spacer(40),
  para("Who it helps:", { after: 80 }),
  bullet("Students and career-switchers who get one real Assessment Centre and cannot afford to waste it."),
  bullet("Universities and bootcamps that need scalable, repeatable group-exercise practice."),
  bullet("Firms that want candidates to fail in rehearsal, not on assessment day."),
  spacer(80),
  body(
    "What \u201Cgood\u201D looks like in use: the candidate leaves with (1) a pack they actually read, (2) a transcript of a messy table, (3) three highlighted moments with a better line, (4) one structural habit to change \u2014 for example, open with the ask, not a life story."
  ),

  h1("6.  Iterations and reflections"),
  body(
    "The product that shipped is not the first design. Live use exposed places where \u201Clet the LLM decide\u201D was the wrong conductor. The important lesson: models generate language; the room must own time, floor, and social rules."
  ),

  table([W3A, W3B, W3C], [
    [cell("Issue", W3A, { header: true }), cell("What happened", W3B, { header: true }), cell("What we changed", W3C, { header: true })],
    [
      cell("Null interrupt prior", W3A, { fill: ALT }),
      cell("POST /api/sessions 500: float(None) because JSON null was present.", W3B, { fill: ALT }),
      cell("Treat None as the personality default. exclude_none=True on outbound payloads.", W3C, { fill: ALT }),
    ],
    [
      cell("Geo-blocked models", W3A),
      cell("OpenAI / Gemini 403 \u201Cnot available in your region\u201D. Invalid google/gemini-2.0-flash 400 crashed the chain; panelists lost words.", W3B),
      cell("Default to DeepSeek. Skip 400/403/404/429 and walk a fallback list (Qwen, Llama, Mistral).", W3C),
    ],
    [
      cell("TTS failures", W3A, { fill: ALT }),
      cell("Qwen 400 on speed: 1.02. Microsoft 502. Voices went silent.", W3B, { fill: ALT }),
      cell("Omit speed except known providers. Pin Kokoro. Remember last-good TTS.", W3C, { fill: ALT }),
    ],
    [
      cell("UI still \u201CAI dark\u201D", W3A),
      cell("Browser cached the old CSS after a cream restyle.", W3B),
      cell("Cache-bust query (?v=paper12) and no-store headers on static assets.", W3C),
    ],
    [
      cell("Wrap with 3 minutes left", W3A, { fill: ALT }),
      cell("The model guessed wrap / intent: wrap locked the room early.", W3B, { fill: ALT }),
      cell("Official clock = duration \u2212 elapsed, injected into prompts. Wrap only at \u2264 30s when the director says WRAP THE DISCUSSION.", W3C, { fill: ALT }),
    ],
    [
      cell("Presentation spoke once", W3A),
      cell("After \u201Cno interrupts\u201D work, each AI dumped one long speech and sat down.", W3B),
      cell("Round-robin one point, many laps, all agents, no interrupts. Wrap writes speak_order + slices.", W3C),
    ],
    [
      cell("Then discussion went quiet", W3A, { fill: ALT }),
      cell("A dice roll random() > prior * 0.4 threw away most yes votes. One shared policy poisoned both floors.", W3B, { fill: ALT }),
      cell("Split two workflows: discussion (barge-in) vs presentation (ordered rotation). Watch agent-on-agent barge-in.", W3C, { fill: ALT }),
    ],
    [
      cell("Talking over itself", W3A),
      cell("Scripts were regenerated while audio was still playing.", W3B),
      cell("Generate once, play through. Interrupt stops playback, then a new script.", W3C),
    ],
  ]),
  caption("Table 5. Build iterations that changed the product, not just the logs."),
  spacer(80),

  h2("6.1  What we would do the same"),
  bullet("Keep LangGraph nodes as workers and the WebSocket room as conductor. Mixing those two is how wrap-too-early happened."),
  bullet("Keep concurrent interrupt votes. A single \u201Cdoes anyone want to talk?\u201D call cannot encode personality."),
  bullet("Keep the coach off-camera and the assessor on a hidden rubric. One model doing all three jobs would leak answers into the table."),
  bullet("Keep the visual brief extreme on purpose. A cream print desk reads as an Assessment Centre. A dark SaaS dashboard does not."),

  h2("6.2  What we would not do again"),
  bullet("Do not let the language model own the clock. Remaining time is a fact, not a vibe."),
  bullet("Do not share one floor policy across discussion and presentation. They are different games."),
  bullet("Do not trust a model ID from a blog post. Region blocks and retired slugs will 400 the whole chain unless fallbacks are first-class."),
  bullet("Do not restyle CSS without busting cache. Candidates will swear the app is still dark."),

  h2("6.3  Honest limits of this version"),
  bullet("Six seats are in the data model; the UI ships three so the table stays audible."),
  bullet("True duplex speech-to-speech (a live voice agent per panelist) would be three parallel audio sessions. This version uses text agents + OpenRouter TTS + live partials, which already supports rational interruption and is cheaper to run."),
  bullet("There is no login or history store. Sessions live in memory for the demo."),
  spacer(80),
  body(
    "Those are the next two steps, not blockers for a working rehearsal. The demonstration already does the thing the original brief asked for: a candidate can pick an industry, sit with three voiced peers, be interrupted for a reason, present as a team, and then highlight a line and ask how to do it better."
  ),

  h1("7.  How to run the demonstration"),
  ...promptBlock("Local run", [
    "cd ploymer",
    "python -m venv .venv",
    ".\\.venv\\Scripts\\Activate.ps1",
    "pip install -r requirements.txt",
    "copy .env.example .env",
    "# paste OPENROUTER_API_KEY from https://openrouter.ai/keys",
    "python run.py",
  ]),
  body(
    "Open http://127.0.0.1:8787. Chrome is best (live speech recognition). Hold Space or click the microphone. Demo timings default to 2 minutes prep / 5 minutes discussion / 3 minutes presentation. Uncheck the box for a full 10 / 20 / 8."
  ),
  spacer(200),
  new Paragraph({
    border: { top: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 10 } },
    spacing: { before: 200, after: 80 },
    children: [
      new TextRun({
        text: "End of write-up. BriefRoom is a rehearsal for the table you cannot otherwise practise.",
        font: "Arial",
        size: 20,
        italics: true,
        color: MUTED,
      }),
    ],
  }),
];

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22, color: INK } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: INK },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: ACCENT },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "\u2022",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: ACCENT, space: 6 } },
              spacing: { after: 120 },
              children: [
                new TextRun({ text: "BriefRoom", font: "Arial", size: 18, bold: true, color: INK }),
                new TextRun({ text: "\t", font: "Arial", size: 18 }),
                new TextRun({
                  text: "AI Assessment Centre demonstration",
                  font: "Arial",
                  size: 18,
                  color: MUTED,
                }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
              border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } },
              spacing: { before: 80 },
              children: [
                new TextRun({
                  text: "Confidential to the demonstration  ·  August 2026",
                  font: "Arial",
                  size: 16,
                  color: MUTED,
                }),
                new TextRun({ text: "\t", font: "Arial", size: 16 }),
                new TextRun({ text: "Page ", font: "Arial", size: 16, color: MUTED }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: MUTED }),
                new TextRun({ text: " of ", font: "Arial", size: 16, color: MUTED }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Arial", size: 16, color: MUTED }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

const out = path.join(__dirname, "..", "BriefRoom-AI-Demo-Journey.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(out, buffer);
  console.log("Wrote", out, buffer.length, "bytes");
});
