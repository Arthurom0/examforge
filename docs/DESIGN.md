# ExamForge — structure and data model

## Project layout

```
examforge/
├── Makefile                 # make setup / make dev / make test
├── dev.sh                   # same as make dev, for machines without make
├── .env.example             # ANTHROPIC_API_KEY, ANTHROPIC_MODEL, paths
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, router registration
│   │   ├── config.py        # settings loaded from .env
│   │   ├── db.py            # SQLite engine + session dependency
│   │   ├── models.py        # SQLModel tables (below)
│   │   ├── schemas.py       # Pydantic schemas: LLM JSON contract + API I/O
│   │   ├── routers/         # courses, documents, exercises, generation, attempts, stats
│   │   └── services/
│   │       ├── extraction.py      # PyMuPDF text + Tesseract OCR fallback, chunking
│   │       ├── booklet_parser.py  # split TD booklets into exercises / sub-questions
│   │       ├── retrieval.py       # BM25 keyword search over chunks (FR/EN, accent-insensitive)
│   │       ├── llm.py             # Claude calls: generate, variants, solve (validated JSON)
│   │       ├── prompts.py         # prompt templates
│   │       └── stats.py           # success rates, weak-spot topic ranking
│   └── tests/
├── frontend/                # React + Vite + Tailwind + KaTeX
│   └── src/
│       ├── pages/           # Library, Booklet review, Generate, Practice, Dashboard, Print
│       ├── components/      # Math renderer, ProblemCard, charts, layout
│       └── api.ts           # typed fetch client
└── data/                    # created at runtime: examforge.db + uploaded PDFs (git-ignored)
```

## Data model (SQLite via SQLModel)

| Table | Key fields | Notes |
|---|---|---|
| **Course** | id, name, created_at | "Mécanique des fluides", "Thermodynamique" |
| **Chapter** | id, course_id, name, position | Ordered within a course |
| **Document** | id, course_id, chapter_id?, kind (`lecture` / `exam` / `booklet`), filename, stored_path, page_count, ocr_used, status, error | One uploaded PDF. Booklets are a distinct kind |
| **Chunk** | id, document_id, course_id, chapter_id?, page, text | ~1200-char overlapping windows used for retrieval |
| **BookletExercise** | id, document_id, course_id, chapter_id?, label ("Exercice 3"), position, statement, given_data, sub_questions (JSON), correction?, correction_source (`none` / `booklet` / `ai`), page_start, page_end, topic_tags (JSON), reviewed | Editable split; `ai` corrections are shown as unverified |
| **ProblemSet** | id, course_id, chapter_id?, mode (`standard` / `weak_spot` / `variant`), params (JSON), source_exercise_id?, created_at | One generation request |
| **Problem** | id, set_id, course_id, chapter_id?, type (`mcq` / `numerical` / `derivation` / `conceptual`), difficulty (`easy` / `medium` / `exam`), language (`fr` / `en`), statement, given_data (JSON list of {symbol, value, unit, description}), choices (JSON)?, answer, solution_steps (JSON list), topic_tags (JSON), self_check | Validated against the Pydantic schema before saving |
| **Attempt** | id, origin (`generated` / `booklet`), problem_id?, exercise_id?, course_id, chapter_id?, topic_tags (JSON), result (`correct` / `partial` / `wrong`), score (1 / 0.5 / 0), created_at | Topics copied at attempt time so stats stay stable |

Topics are free-form tags the model assigns (normalized to lowercase, accents kept) and that you can edit on booklet exercises.

## Generation pipeline

1. Build a query from the chapter name + topic focus (weak-spot mode picks the lowest-success topics, with a minimum attempt count and a smoothing prior so one wrong answer does not dominate).
2. BM25 retrieves the top course chunks for that course/chapter; 2–3 booklet exercises from the same chapter are added as style references.
3. Claude returns a `ProblemBatch` via structured outputs (Pydantic schema), with instructions to use SI units, realistic values, LaTeX math, and to self-check each solution (recompute the answer, check units and orders of magnitude) before returning.
4. The batch is validated, then saved as a ProblemSet.

Variant mode feeds one booklet exercise and asks for changed values, reversed unknowns, or an added twist. Solve mode produces a correction stored with `correction_source = ai` and labeled "AI-generated, unverified".

## Decisions taken by default

- Retrieval is BM25 keyword search (no embedding model to download, works offline, handles FR/EN via accent folding and light stemming).
- PDF export renders the set in a print-optimized page with KaTeX and uses the browser's "Save as PDF", which keeps equations crisp; a toggle chooses solutions inline or in an appendix.
- Model defaults to `claude-opus-5-5`, overridable with `ANTHROPIC_MODEL` in `.env`.
