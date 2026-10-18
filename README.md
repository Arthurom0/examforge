# ExamForge

A local web app that turns your engineering course PDFs into practice problems. Upload lecture slides, polycopiés, past exams and tutorial booklets (fascicules de TD) per course and chapter, then generate problems with Claude that match your professors' notation and level. Worked solutions are revealed step by step with KaTeX, and every attempt you mark (correct / partial / wrong) feeds a dashboard and a weak-spot mode.

Everything runs on your machine: the database is a SQLite file and your PDFs stay in `data/`. Only the text excerpts needed for a generation request are sent to the Claude API.

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

## Requirements

- **Python 3.10+**
- **Node.js 18+** (includes npm)
- **Tesseract** with French and English language packs (only needed for scanned PDFs):
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng`
  - Windows: install from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki), tick "French" under additional languages, and add the install folder (e.g. `C:\Program Files\Tesseract-OCR`) to your PATH.
- An **Anthropic API key** from [console.anthropic.com](https://console.anthropic.com) (needed for generation, solve, variants, tagging and re-transcription; uploading and practicing booklet exercises work without it).

## Setup and run

```bash
cd examforge
cp .env.example .env        # then open .env and paste your key after ANTHROPIC_API_KEY=
make dev                    # or: python3 run.py   (Windows: python run.py)
```

The first run creates a virtual environment in `.venv`, installs the Python and npm dependencies, then starts:

- the backend on http://127.0.0.1:8000 (API docs at http://127.0.0.1:8000/docs)
- the frontend on http://localhost:5173 (opens in your browser)

Ctrl+C stops both. If you forget to create `.env`, the launcher copies `.env.example` for you; restart after adding the key.

### Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | (empty) | Your API key. Never commit this file (`.env` is git-ignored). |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Model used for every request. |
| `ANTHROPIC_EFFORT` | `high` | `low` … `max`. Higher means more careful solutions, but slower and pricier. |
| `EXAMFORGE_DATA_DIR` | `data` | Where the SQLite database and uploaded PDFs are stored. |
| `OCR_LANGS` | `fra+eng` | Tesseract languages. |

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
- **Generation error about the API key**: check `.env` at the repo root, then restart `make dev`.
- **Port already in use**: stop the other process on 8000 or 5173, or change the ports in `run.py` and `frontend/vite.config.ts`.

## Project layout

```
backend/   FastAPI app (app/), services (extraction, booklet parser, retrieval, LLM, stats), tests
frontend/  React + Vite + Tailwind + KaTeX
docs/      design notes
data/      created at runtime: examforge.db and uploads (git-ignored)
run.py     one-command launcher used by `make dev`
```
