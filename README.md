# Virtual Town Hall — Multi-Species Interaction Demo

Project Platypus · Team 56 · demonstration for 24 July.

Three species/community representatives sit in a Zoom-style call. You put a policy
to the floor (typed or spoken) and each one argues from its **own self-interest**.
You can also upload a full policy document and get back a Word report.

**Core rule:** the AI (Gemini) only *phrases* arguments. Every fact comes from the
verified evidence base (`evidence.json`, built from IUCN Red List + GBIF). Conflict
between representatives is surfaced on purpose — it is resolved at a system layer
*above* them, never inside any one representative.

## Representatives
| Representative | Type | Data status | Why |
|---|---|---|---|
| Great White Shark (*Carcharodon carcharias*) | species | data-rich | Vulnerable, strong IUCN + GBIF record |
| Australian Sea Lion (*Neophoca cinerea*) | species | data-rich | Endangered, endemic |
| Beach Users | community | **data-poor** | Deliberately weak evidence — shows confidence-flagging in action |

## Files
- `build_evidence.py` — pulls live GBIF counts, tags IUCN facts by tier/confidence, writes `evidence.json`
- `server.py` — Flask backend (live replies + document analysis). **Holds the API key.**
- `index.html` — Zoom-style UI, two tabs: Live call / Document analysis
- `START_WINDOWS.bat` — one-click launcher (uses `py`, not `python`)

## Setup (Windows)
1. Get a free Gemini key at https://aistudio.google.com
2. Open `server.py`, replace `PASTE_YOUR_KEY_HERE` with your key
   (or set `GEMINI_API_KEY` in your environment instead).
3. Double-click `START_WINDOWS.bat`.
4. Open http://localhost:5000

Manual alternative:
```
py -m pip install flask google-generativeai python-docx pdfplumber requests
py build_evidence.py
py server.py
```

## Notes / known gotchas
- On Windows, Python is often `py`, not `python`. The `.bat` handles this.
- Make sure all files sit in the **same folder on the same drive**.
- If a "app execution alias" intercepts `py`, disable it in
  Settings → Apps → Advanced app settings → App execution aliases.
- Model: primary `gemini-3.5-flash`, falls back to `gemini-2.5-flash` on 503.
- **Rotate your API key after the demo.** Never commit `server.py` with a real key.

## Document analysis
Upload `.txt`, `.docx`, or `.pdf`. Long documents are split into ~6,000-character
chunks; every representative reviews every chunk; results are assembled into one
`policy_analysis.docx` with, per representative: Support points, Opposition points,
Proposed improvements — each row carrying a confidence flag and its evidence basis.
