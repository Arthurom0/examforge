# ExamForge

A local web app that turns your engineering course PDFs into practice problems. Upload lecture slides, polycopiés, past exams and tutorial booklets (fascicules de TD) per course and chapter, then generate problems with Claude that match your professors' notation and level. Worked solutions are revealed step by step with KaTeX, and every attempt you mark (correct / partial / wrong) feeds a dashboard and a weak-spot mode.

Everything runs on your machine, as a Mac app or from source: the database is a SQLite file and your PDFs stay in `data/`. Only the text excerpts needed for a generation request are sent to the Claude API.

## Features

- **Library**: courses → chapters → documents. Three upload types: lecture material, past exam, tutorial booklet. Text is extracted with PyMuPDF; scanned pages fall back to Tesseract OCR (French + English).
- **Booklet parsing**: booklets are split into exercises ("Exercice 1", "Ex. 2", "EXERCICE IV", "Problème 3"…), with sub-questions (a/b/c, 1)/2)), given data, and the correction when the booklet has one, either right after the exercise or in a "Corrigés" section at the end. "Chapitre N" / "TD N" headings assign exercises to chapters (created if needed).
- **Review the split**: fix anything the parser got wrong: edit fields, split at the cursor, merge with the next exercise, add or delete. "Re-transcribe with Claude" re-reads the exercise from the page images and rewrites it in LaTeX, which fixes equations mangled by extraction or OCR.
- **Generate**: pick course/chapter, difficulty (easy / medium / exam-level), types (MCQ, numerical, derivation, conceptual), language (FR/EN) and count. The prompt includes the most relevant chunks of your course (BM25 keyword search) and 2–3 similar booklet exercises as style references. Claude must use realistic values with SI units and self-check each solution before answering; the JSON output is validated and retried once if anything is off.
- **Variant mode**: from any booklet exercise, generate variants with changed values, reversed unknowns, or an added twist.
- **Solve mode**: for booklet exercises without a correction, generate a step-by-step solution, clearly labeled *AI-generated, unverified*.
- **Tracking**: mark each attempt; booklet exercises and generated problems are tracked separately, per chapter and per topic.
- **Weak-spot mode**: generation targets the topics with your lowest (smoothed) success rate.
- **Dashboard**: success rate per course and chapter (generated vs booklet), over time (weekly/daily), and per topic.
- **PDF export**: a print layout of any problem set with solutions at the end, inline, or omitted; use the browser's "Save as PDF" (equations stay sharp).
- Dark mode (follows your system, toggle in the header).

## Mac app (.dmg)

ExamForge also ships as a regular macOS app: it opens in its own window, lives in the Dock, and needs no browser and no terminal. Inside, an Electron shell starts the bundled Python engine on a private localhost port and shows the same interface.

### Get the .dmg

**Option A: build it on GitHub (no setup on your Mac).** In the repo, open **Actions → Build macOS app → Run workflow**. When it finishes, download `ExamForge-macOS-arm64` (Apple Silicon: M1–M4) or `ExamForge-macOS-x64` (Intel) from the run's **Artifacts**, and unzip it to get the `.dmg`. Pushing a tag like `v0.2.0` also triggers it.

**Option B: build it on your Mac.** You need Python 3.10+, Node 18+ and the Xcode command-line tools (`xcode-select --install`). Then:

```bash
make dmg        # or ./desktop/build.sh
```

The result is `desktop/release/ExamForge-<version>-<arch>.dmg`, built for your Mac's processor.

### Install and first launch

1. Open the `.dmg` and drag **ExamForge** to **Applications**.
2. The app is not signed with an Apple Developer ID, so the first time macOS blocks it. **Right-click → Open → Open** (on recent macOS: try to open it once, then **System Settings → Privacy & Security → Open Anyway**). Alternatively run `xattr -dr com.apple.quarantine /Applications/ExamForge.app`. You only do this once.
3. Go to **Settings** in the app, pick an AI provider (Claude by default) and paste its API key. Keys are stored in `~/Library/Application Support/ExamForge/.env`, readable only by you. Ollama runs locally and needs no key.
4. For scanned PDFs, install Tesseract once with `brew install tesseract tesseract-lang`; the app finds it automatically.

Your courses, PDFs and progress live in `~/Library/Application Support/ExamForge` (the **Show in Finder** button in Settings opens it). Updating the app by dragging a newer version into Applications keeps them.

**Export PDF** in the app opens a native save dialog and writes the PDF directly.

`make app` opens the desktop window from the source tree without packaging, which is handy while developing.

## Running from source (browser)

### Requirements

- **Python 3.10+**
- **Node.js 18+** (includes npm)
- **Tesseract** with French and English language packs (only needed for scanned PDFs):
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng`
  - Windows: install from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki), tick "French" under additional languages, and add the install folder (e.g. `C:\Program Files\Tesseract-OCR`) to your PATH.
- An API key for one AI provider (see [AI providers](#ai-providers)), or Ollama running locally. It is needed for generation, solve, variants, tagging and re-transcription; uploading and practicing booklet exercises work without it.

### Setup and run

```bash
cd examforge
cp .env.example .env        # optional: paste a key there, or set it later in Settings
make dev                    # or: python3 run.py   (Windows: python run.py)
```

The first run creates a virtual environment in `.venv`, installs the Python and npm dependencies, then starts:

- the backend on http://127.0.0.1:8000 (API docs at http://127.0.0.1:8000/docs)
- the frontend on http://localhost:5173 (opens in your browser)

Ctrl+C stops both. If you forget to create `.env`, the launcher copies `.env.example` for you; restart after adding the key.

#### Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `EXAMFORGE_PROVIDER` | `anthropic` | Which AI provider to use: `anthropic`, `openai`, `google`, `deepseek`, `xai` or `ollama`. |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY` | (empty) | One key per provider. Never commit this file (`.env` is git-ignored). |
| `<PROVIDER>_MODEL` (e.g. `OPENAI_MODEL`) | see below | Model for that provider. |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Where Ollama listens. |
| `ANTHROPIC_EFFORT` | `high` | Claude only: `low` … `max`. Higher means more careful solutions, but slower and pricier. |
| `EXAMFORGE_DATA_DIR` | `data` | Where the SQLite database and uploaded PDFs are stored. |
| `OCR_LANGS` | `fra+eng` | Tesseract languages. |

## AI providers

Pick the provider in **Settings**; every one goes through the same prompts, JSON schema, validation (units, MCQ answers, at least two solution steps, a written self-check) and one automatic retry.

| Provider | Default model | Key from | Notes |
|---|---|---|---|
| Claude (Anthropic), default | `claude-opus-5-5` | console.anthropic.com | Native structured outputs and the effort setting. |
| OpenAI | `gpt-6-astra` | platform.openai.com | |
| Google AI (Gemini) | `gemini-4-argon` | aistudio.google.com | Uses Gemini's OpenAI-compatible endpoint. |
| DeepSeek | `deepseek-v4-pro` | platform.deepseek.com | Text only: no re-transcription from page images. |
| Grok (xAI) | `grok-4.7` | console.x.ai | |
| Ollama (local) | `qwen3:8b` | none | Install Ollama, run `ollama pull qwen3:8b`. Text only. Slower and weaker on exam-level problems. |

The model field accepts any model name the provider offers. To add a provider that speaks the OpenAI Chat Completions format, append an entry to `PROVIDERS` in `backend/app/services/providers.py`.

## Suggested workflow

1. **Library**: create a course ("Mécanique des fluides"), add chapters, upload the polycopié and slides per chapter, past exams, and the TD booklet (leave its chapter empty to detect chapters from headings).
2. **Review split** on the booklet: check that exercises were cut correctly, fix what's off, then click **Auto-tag topics** so booklet attempts are tracked per topic.
3. **Booklet exercises**: work through the original exercises, reveal corrections, mark attempts, use **Solve with AI** where the booklet has no correction, or **Variants…** for more practice on one exercise.
4. **Generate**: create sets for a chapter; turn on **weak-spot mode** once you have some attempts.
5. **Export PDF** from a set for offline revision; check the **Dashboard** to see where you stand.

Generation takes roughly 30 s to 2 min per set, depending on the count, difficulty and effort setting.

## How it works

- **Extraction**: PyMuPDF reads each page; pages with almost no text but images are rendered at 300 dpi and OCR'd with Tesseract (`--psm 6`). Common glyph and unit artifacts are repaired (ligatures, symbol-font Greek letters, `m/s2` → `m/s²`, `10-5` → `10^-5`). Text is stored per page and in ~1200-character overlapping chunks.
- **Retrieval**: BM25 over the course's chunks, accent-insensitive with French/English stop words and light stemming; chunks from the selected chapter get a boost. No embedding model to download.
- **Generation**: one streamed Claude request with adaptive thinking and structured outputs (the Pydantic `ProblemBatch` schema in `backend/app/schemas.py`). Extra checks the schema can't express (MCQ answer matches a choice, numerical problems have units and a number in the answer, at least two solution steps…) trigger one retry with the errors fed back.
- **Weak spots**: per-topic success rate smoothed toward 50 % with a prior of two attempts, so one mistake doesn't dominate; topics above 85 % are skipped.

The structure and data model are described in [docs/DESIGN.md](docs/DESIGN.md).

## Tests

```bash
make test      # or: cd backend && ../.venv/bin/python -m pytest -q
```

The tests build small PDFs on the fly (text lecture, text booklet, scanned booklet) and cover extraction, OCR, booklet splitting, retrieval, and the full API flow with Claude mocked out. The OCR test is skipped if Tesseract isn't installed.

## Troubleshooting

- **"No text found" on a scanned PDF**: Tesseract isn't installed or not on PATH. Install it (see Requirements) and click **Re-extract** on the document.
- **Equations look garbled**: that's PDF text extraction. Open the exercise in **Review split** and use **Re-transcribe with Claude**. For lecture material it matters less: Claude is told the excerpts may be garbled and rewrites math in LaTeX.
- **Exercises split badly**: use the **Raw text** tab to split at the cursor, or merge with the next exercise. Re-extracting the document re-runs the parser and discards manual fixes (your past attempts stay in the stats).
- **Generation error about the API key**: set it in **Settings** (from source, it is saved to `.env` at the repo root).
- **Mac app says it stopped or could not start**: the engine log is in `~/Library/Application Support/ExamForge/logs/engine.log`.
- **Port already in use**: stop the other process on 8000 or 5173, or change the ports in `run.py` and `frontend/vite.config.ts`.

## Project layout

```
backend/   FastAPI app (app/), services (extraction, booklet parser, retrieval, LLM, stats), tests
frontend/  React + Vite + Tailwind + KaTeX
docs/      design notes
data/      created at runtime: examforge.db and uploads (git-ignored)
desktop/   Electron shell (main.js, preload.js), build script for the .dmg, app icon
run.py     one-command launcher used by `make dev`
```
