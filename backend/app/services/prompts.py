"""Prompt templates for Claude."""
from __future__ import annotations

from ..models import BookletExercise, Chunk

SYSTEM = """You write practice problems for a French engineering student (ESILV, aerospace major) \
preparing exams. You are given excerpts of the student's actual course material and tutorial exercises \
written by their professors. Problems must be solvable from that material, use the same notation, \
conventions and level, and read like exercises those professors would set.

Formatting:
- Markdown, with LaTeX for all math: $...$ inline and $$...$$ for display equations. Never use \\( \\) or \\[ \\].
- Course excerpts come from PDF text extraction, so equations may be garbled; reconstruct them carefully in LaTeX.
- Units in SI with LaTeX formatting (e.g. $\\rho = 1{,}2\\ \\mathrm{kg\\,m^{-3}}$). In French, use a decimal comma.

Numerical problems:
- Use physically realistic values (real fluids, gases, materials, aircraft and engine scales) with correct units.
- The answer must include a value with the right number of significant figures and a unit.

Before returning each problem, self-check it: re-derive the result independently, check dimensional \
homogeneity of every formula, check orders of magnitude against physical intuition, and for MCQ check that \
exactly one option is correct and the distractors reflect typical mistakes. Fix anything that fails, then \
summarize what you verified in `self_check`."""

TYPE_LABELS = {
    "mcq": "multiple choice (exactly 4 options A-D, one correct)",
    "numerical": "numerical calculation (given data with units, numerical answer with unit)",
    "derivation": "derivation (derive or prove a relation step by step; answer is the final expression)",
    "conceptual": "conceptual short answer (explain a phenomenon or justify a modeling choice in a few sentences)",
}
DIFFICULTY_LABELS = {
    "easy": "easy: direct application of one course formula or concept",
    "medium": "medium: two or three steps, combining concepts from the chapter",
    "exam": "exam-level: multi-step, comparable to the hardest booklet exercises and past exam questions, "
            "may combine several chapters' tools and require modeling assumptions",
}


def format_chunks(chunks: list[Chunk], doc_names: dict[int, str]) -> str:
    if not chunks:
        return "(no course material uploaded for this scope)"
    return "\n\n".join(
        f'<excerpt source="{doc_names.get(c.document_id, "document")}" page="{c.page}">\n{c.text}\n</excerpt>'
        for c in chunks
    )


def format_exercise(e: BookletExercise, include_correction: bool = False) -> str:
    parts = [f"{e.label}\n{e.statement}"]
    if e.given_data and e.given_data not in e.statement:
        parts.append(f"Données : {e.given_data}")
    for q in e.sub_questions:
        parts.append(f"{q.get('label')}) {q.get('text')}")
    if include_correction and e.correction:
        parts.append(f"Correction:\n{e.correction}")
    return "\n".join(parts)


def format_reference_exercises(exercises: list[BookletExercise]) -> str:
    if not exercises:
        return "(no tutorial booklet exercises available)"
    return "\n\n".join(f"<booklet_exercise>\n{format_exercise(e)}\n</booklet_exercise>" for e in exercises)


def generation_prompt(*, course: str, chapter: str | None, excerpts: str, references: str, count: int,
                      types: list[str], difficulty: str, language: str, focus_topics: list[str] | None,
                      user_focus: str | None) -> str:
    lang = "French" if language == "fr" else "English"
    plan = ", ".join(f"{t} ({TYPE_LABELS[t]})" for t in types)
    focus = ""
    if focus_topics:
        focus += ("\nThe student is weakest on these topics; target them (spread the problems across them): "
                  + ", ".join(focus_topics) + ".")
    if user_focus:
        focus += f"\nThe student asked to focus on: {user_focus}."
    return f"""<course>{course}</course>
<chapter>{chapter or "whole course"}</chapter>

<course_material>
{excerpts}
</course_material>

<style_references>
These are exercises from the professors' tutorial booklet. Match their format, notation, phrasing and level. \
Do not copy them.
{references}
</style_references>

Write {count} new practice problem(s) in {lang}.
- Types: distribute the problems over: {plan}. Set each problem's `type` accordingly.
- Difficulty: {DIFFICULTY_LABELS[difficulty]}. Set `difficulty` to "{difficulty}".
- Ground every problem in the course material above; use its notation.{focus}
- Each problem needs a complete worked solution in `solution_steps` (3 to 8 steps), written so a student \
can follow it, with intermediate numerical results where relevant.
- `topic_tags`: 1 to 3 short, reusable tags in {lang} (e.g. "bernoulli", "pertes de charge", "nombre de reynolds")."""


VARIANT_KINDS = {
    "values": "same structure with different, still realistic, numerical values",
    "reversed": "reversed unknowns: give what was asked and ask for what was given",
    "twist": "an added twist: an extra physical effect, constraint or question that deepens the same concept",
}


def variant_prompt(*, course: str, exercise: BookletExercise, excerpts: str, count: int, kinds: list[str],
                   language: str) -> str:
    lang = "French" if language == "fr" else "English"
    kinds_txt = "\n".join(f"- {VARIANT_KINDS[k]}" for k in kinds)
    return f"""<course>{course}</course>

<course_material>
{excerpts}
</course_material>

<original_exercise>
{format_exercise(exercise, include_correction=True)}
</original_exercise>

Write {count} variant(s) of the original exercise in {lang}, for extra practice on the same concept. \
Cycle through these kinds of variation:
{kinds_txt}

Keep the professors' format and notation. Each variant's `title` must start with the kind of change in \
brackets, e.g. "[valeurs] ..." / "[inconnues inversées] ..." / "[variante] ..." (or the English equivalents). \
Use the same `type` as the original would have (usually "numerical" or "derivation"). Each variant needs a \
complete worked solution, and the self-check described in your instructions."""


def solve_prompt(*, course: str, exercise: BookletExercise, excerpts: str, language: str) -> str:
    lang = "French" if language == "fr" else "English"
    return f"""<course>{course}</course>

<course_material>
{excerpts}
</course_material>

<exercise>
{format_exercise(exercise)}
</exercise>

This booklet exercise has no correction. Write a complete step-by-step correction in {lang}, using the \
course's notation and methods, answering every sub-question in order (label steps with the sub-question \
label). Give intermediate and final numerical results with units. Self-check as described in your \
instructions. If the statement is ambiguous or data seems missing (extraction may have lost part of it), \
state the assumption you make in `assumptions` and lower `confidence`."""


def tagging_prompt(*, course: str, chapter_names: dict[int | None, str], exercises: list[BookletExercise]) -> str:
    items = "\n\n".join(
        f'<exercise id="{e.id}" chapter="{chapter_names.get(e.chapter_id, "")}">\n{format_exercise(e)[:1500]}\n</exercise>'
        for e in exercises
    )
    return f"""<course>{course}</course>

{items}

For each exercise, give 1 to 3 short, reusable topic tags (lowercase, in the exercise's language) naming \
the concepts it practices, e.g. "bernoulli", "pertes de charge", "premier principe", "cycle de brayton". \
Reuse the same tag for the same concept across exercises."""


TRANSCRIBE_PROMPT = """These page images contain the tutorial exercise "{label}". Below is the text a PDF \
extractor or OCR produced for it, which may have garbled equations:

<extracted_text>
{raw}
</extracted_text>

Transcribe only this exercise faithfully from the images, in its original language, as Markdown with \
LaTeX math ($...$ and $$...$$). Do not solve it or add anything. Put numerical data in `given_data` \
(as text, one item per line) if the exercise lists data. Split numbered/lettered sub-questions into \
`sub_questions`. If a correction for this exercise appears on these pages, transcribe it in `correction`, \
else leave it empty."""
