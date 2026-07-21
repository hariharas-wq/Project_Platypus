import React, { useState, useRef, useEffect } from "react";

/* ============================================================
   Virtual Species Town Hall — LLM edition
   Project Platypus / Team 56
   Each ambassador is a real Claude call, grounded ONLY in the
   pasted evidence.json. Runs inside the Claude artifact runtime
   (api.anthropic.com is authenticated here — no key needed).
   ============================================================ */

// ---- default evidence (paste your scraped evidence.json over this) ----
const DEFAULT_EVIDENCE = {
  species: {
    great_white: {
      common: "Great White Shark",
      latin: "Carcharodon carcharias",
      status: { value: "Vulnerable", source: "IUCN Red List", tier: 1, confidence: "high" },
      global_decline: { value: "30–49% over three generations (159 years)", source: "IUCN Red List assessment", tier: 1, confidence: "high" },
      generation_length: { value: "53 years", source: "IUCN Red List (current)", tier: 1, confidence: "high" },
      role: { value: "Apex predator — regulates species below it", source: "Ecological consensus", tier: 2, confidence: "high" },
      occurrences_australia: { value: "~38,000 georeferenced sightings", source: "GBIF", tier: 3, confidence: "high" },
    },
    australian_sea_lion: {
      common: "Australian Sea Lion",
      latin: "Neophoca cinerea",
      status: { value: "Endangered", source: "IUCN Red List", tier: 1, confidence: "high" },
      key_threat: { value: "Fisheries bycatch / net entanglement", source: "IUCN Red List assessment", tier: 1, confidence: "high" },
    },
  },
};

const AMBASSADORS = [
  { id: "great_white", name: "Great White Shark", tag: "Species Ambassador", glyph: "🦈", accent: "#5fd0e6", kind: "species" },
  { id: "australian_sea_lion", name: "Australian Sea Lion", tag: "Species Ambassador", glyph: "🦭", accent: "#9db4d6", kind: "species" },
  { id: "beach_users", name: "Beach Users", tag: "Community Ambassador", glyph: "🏄", accent: "#e0b64a", kind: "community" },
];

function evidenceFor(id, ev) {
  const s = ev.species?.[id];
  if (!s) {
    // beach_users has no dataset — deliberately data-poor, demonstrates confidence flagging
    return { common: "Beach Users", note: "No scientific dataset — community stakeholder. Arguments are preference-based, not evidence-graded.", tier: 4, confidence: "low" };
  }
  return s;
}

function buildPrompt(amb, ev, policy) {
  const e = evidenceFor(amb.id, ev);
  return `You are the ambassador for the ${amb.name} at a Virtual Species Town Hall. You argue like a UN ambassador: SELF-INTERESTED, first person, advocating only for your own constituency. You do NOT try to be neutral or balance other species' interests — conflict is resolved by a system layer above you, not within you.

STRICT RULES:
- Ground every factual claim ONLY in the evidence below. Do not invent numbers.
- After any factual claim, you may note its confidence in brackets, e.g. [IUCN, high confidence].
- If the evidence is thin or low-confidence, SAY SO plainly rather than bluffing. Visible uncertainty is a feature.
- 2–4 sentences. Address "Chair". Stay in character.

YOUR EVIDENCE (JSON):
${JSON.stringify(e, null, 2)}

TABLED POLICY:
"${policy}"

Respond now as the ${amb.name} ambassador.`;
}

async function callClaude(prompt) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      messages: [{ role: "user", content: prompt }],
    }),
  });
  const data = await res.json();
  return data.content.filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
}

// browser TTS
function speak(text, pitch, rate) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/\[.*?\]/g, "")); // don't read the confidence brackets aloud
  u.pitch = pitch; u.rate = rate;
  window.speechSynthesis.speak(u);
}

export default function TownHall() {
  const [evidence, setEvidence] = useState(DEFAULT_EVIDENCE);
  const [evidenceText, setEvidenceText] = useState(JSON.stringify(DEFAULT_EVIDENCE, null, 2));
  const [showEvidence, setShowEvidence] = useState(false);
  const [policy, setPolicy] = useState("");
  const [transcript, setTranscript] = useState([]); // {who, text, accent, kind}
  const [speaking, setSpeaking] = useState(null);
  const [running, setRunning] = useState(false);
  const [muted, setMuted] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [transcript, speaking]);

  function applyEvidence() {
    try {
      setEvidence(JSON.parse(evidenceText));
      setShowEvidence(false);
    } catch {
      alert("That isn't valid JSON — paste the contents of evidence.json.");
    }
  }

  async function runRound() {
    if (!policy.trim() || running) return;
    setRunning(true);
    setTranscript([{ who: "Policy Chair", text: `"${policy}" — ambassadors, your responses.`, accent: "#3ecf8e", kind: "chair" }]);

    for (const amb of AMBASSADORS) {
      setSpeaking(amb.id);
      let text;
      try {
        text = await callClaude(buildPrompt(amb, evidence, policy));
      } catch (e) {
        text = `[connection issue — the ${amb.name} ambassador could not respond]`;
      }
      const pitch = amb.id === "australian_sea_lion" ? 1.1 : amb.id === "great_white" ? 0.8 : 1.0;
      const rate = amb.id === "great_white" ? 0.92 : 1.0;
      setTranscript((t) => [...t, { who: amb.name, text, accent: amb.accent, kind: amb.kind }]);
      if (!muted) {
        speak(text, pitch, rate);
        // wait for speech to finish (rough) before next speaker
        await new Promise((r) => {
          const check = setInterval(() => {
            if (!window.speechSynthesis || !window.speechSynthesis.speaking) { clearInterval(check); r(); }
          }, 300);
          setTimeout(() => { clearInterval(check); r(); }, 20000);
        });
      } else {
        await new Promise((r) => setTimeout(r, 700));
      }
    }
    setSpeaking(null);
    setTranscript((t) => [...t, { who: "Policy Chair", text: "That concludes the round. Conflicts between ambassadors are resolved at the system layer above them — not within any single representative.", accent: "#3ecf8e", kind: "chair" }]);
    setRunning(false);
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#0b1220", color: "#e7eef6", fontFamily: "Inter, system-ui, sans-serif" }}>
      {/* top bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 18px", background: "#0a0f1a", borderBottom: "1px solid #1a2436" }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>Virtual Species Town Hall — Coastal Policy Session</div>
          <div style={{ color: "#8fa3bd", fontSize: 12 }}>Project Platypus · grounded in live evidence</div>
        </div>
        <button onClick={() => setShowEvidence((s) => !s)} style={btnGhost}>{showEvidence ? "Hide" : "Load"} evidence.json</button>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "rgba(229,72,77,.14)", color: "#e5484d", fontSize: 12, fontWeight: 600, padding: "4px 9px", borderRadius: 20 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#e5484d" }} />LIVE
        </span>
      </div>

      {showEvidence && (
        <div style={{ padding: 14, background: "#0d1524", borderBottom: "1px solid #1a2436" }}>
          <div style={{ fontSize: 12, color: "#8fa3bd", marginBottom: 6 }}>Paste the output of <code>build_evidence.py</code>. Ambassadors argue only from this.</div>
          <textarea value={evidenceText} onChange={(e) => setEvidenceText(e.target.value)} spellCheck={false}
            style={{ width: "100%", height: 160, background: "#0e1626", color: "#bfe6f1", border: "1px solid #26344c", borderRadius: 8, padding: 10, fontFamily: "monospace", fontSize: 12 }} />
          <button onClick={applyEvidence} style={{ ...btnPrimary, marginTop: 8 }}>Apply evidence</button>
        </div>
      )}

      {/* participant tiles */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, padding: 12 }}>
        <Tile name="Policy Chair (You)" tag="Chair" glyph="🎙️" accent="#3ecf8e" active={running && speaking === null} />
        {AMBASSADORS.map((a) => (
          <Tile key={a.id} name={a.name} tag={a.tag} glyph={a.glyph} accent={a.accent} active={speaking === a.id} />
        ))}
      </div>

      {/* transcript */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "8px 16px" }}>
        {transcript.length === 0 && (
          <div style={{ color: "#5f7290", textAlign: "center", marginTop: 40, fontSize: 14 }}>
            Table a policy below. Each ambassador will respond in turn, live, grounded in the evidence.
          </div>
        )}
        {transcript.map((m, i) => (
          <div key={i} style={{ margin: "10px 0", maxWidth: 820 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".4px", textTransform: "uppercase", color: m.accent, marginBottom: 3 }}>{m.who}</div>
            <div style={{ background: "rgba(3,8,16,.6)", border: "1px solid #223047", borderRadius: 10, padding: "10px 14px", fontSize: 15, lineHeight: 1.5 }}
              dangerouslySetInnerHTML={{ __html: highlightConf(m.text) }} />
          </div>
        ))}
        {speaking && <div style={{ color: "#8fa3bd", fontSize: 13, fontStyle: "italic", margin: "8px 0" }}>{AMBASSADORS.find((a) => a.id === speaking)?.name} is responding…</div>}
      </div>

      {/* controls */}
      <div style={{ background: "#0a0f1a", borderTop: "1px solid #1a2436", padding: 12 }}>
        <div style={{ display: "flex", gap: 8, maxWidth: 900, margin: "0 auto" }}>
          <input value={policy} onChange={(e) => setPolicy(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runRound()}
            placeholder="Table a policy — e.g. 'Install lethal drumlines along all popular beaches'"
            style={{ flex: 1, background: "#0e1626", border: "1px solid #26344c", color: "#e7eef6", borderRadius: 10, padding: "11px 14px", fontSize: 14 }} />
          <button onClick={runRound} disabled={running} style={{ ...btnPrimary, opacity: running ? 0.5 : 1 }}>
            {running ? "Round in progress…" : "Table policy"}
          </button>
          <button onClick={() => setMuted((m) => !m)} style={btnGhost}>{muted ? "🔇 Muted" : "🔊 Voice"}</button>
        </div>
        <div style={{ color: "#5f7290", fontSize: 11.5, textAlign: "center", marginTop: 8 }}>
          Each response is a live, self-interested argument grounded in evidence.json. Confidence flags shown in blue. Best in Chrome.
        </div>
      </div>
    </div>
  );
}

function Tile({ name, tag, glyph, accent, active }) {
  return (
    <div style={{
      position: "relative", background: "#141d2e", border: "1px solid #22304a",
      borderRadius: 12, padding: "18px 10px", textAlign: "center", minHeight: 96,
      outline: active ? `3px solid ${accent}` : "none", outlineOffset: -3, transition: "outline .2s",
    }}>
      <div style={{ position: "absolute", top: 8, left: 8, fontSize: 10, color: "#8fa3bd", background: "rgba(4,9,18,.5)", padding: "2px 7px", borderRadius: 6 }}>{tag}</div>
      <div style={{ fontSize: 38, filter: active ? `drop-shadow(0 0 10px ${accent})` : "none" }}>{glyph}</div>
      <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 6, color: active ? accent : "#e7eef6" }}>{name}</div>
    </div>
  );
}

// turn [IUCN, high confidence] into a colored chip inline
function highlightConf(text) {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc.replace(/\[([^\]]+)\]/g, '<span style="font-size:11px;background:#12283a;border:1px solid #274b62;color:#9fd7e4;padding:1px 7px;border-radius:20px;margin:0 2px;">$1</span>');
}

const btnPrimary = { background: "#5fd0e6", color: "#04222b", border: "none", borderRadius: 10, padding: "11px 18px", fontWeight: 600, fontSize: 14, cursor: "pointer" };
const btnGhost = { background: "#1b2740", color: "#e7eef6", border: "none", borderRadius: 10, padding: "9px 14px", fontSize: 13, cursor: "pointer" };
