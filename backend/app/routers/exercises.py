"""Booklet exercises: review/fix the split, solve without correction, re-transcribe, tag."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Attempt, BookletExercise, Chapter, Course, Document
from ..schemas import ExerciseTranscription, ExerciseUpdate, SplitRequest, TagBatch
from ..services import extraction, llm, prompts, retrieval
from ..services.booklet_parser import reparse_block

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


def _get(session: Session, ex_id: int) -> BookletExercise:
    ex = session.get(BookletExercise, ex_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    return ex


def _with_stats(session: Session, exercises: list[BookletExercise]) -> list[dict]:
    ids = [e.id for e in exercises]
    attempts = session.exec(select(Attempt).where(Attempt.exercise_id.in_(ids))).all() if ids else []
    by_ex: dict[int, list[Attempt]] = {}
    for a in attempts:
        by_ex.setdefault(a.exercise_id, []).append(a)
    out = []
    for e in exercises:
        ea = sorted(by_ex.get(e.id, []), key=lambda a: a.created_at)
        out.append({**e.model_dump(), "attempts": len(ea), "last_result": ea[-1].result if ea else None})
    return out


@router.get("")
def list_exercises(course_id: Optional[int] = None, chapter_id: Optional[int] = None,
                   document_id: Optional[int] = None, session: Session = Depends(get_session)):
    stmt = select(BookletExercise)
    if course_id is not None:
        stmt = stmt.where(BookletExercise.course_id == course_id)
    if chapter_id is not None:
        stmt = stmt.where(BookletExercise.chapter_id == chapter_id)
    if document_id is not None:
        stmt = stmt.where(BookletExercise.document_id == document_id)
    rows = session.exec(stmt.order_by(BookletExercise.document_id, BookletExercise.position)).all()
    return _with_stats(session, list(rows))


@router.get("/{ex_id}")
def get_exercise(ex_id: int, session: Session = Depends(get_session)):
    return _with_stats(session, [_get(session, ex_id)])[0]


@router.patch("/{ex_id}")
def update_exercise(ex_id: int, body: ExerciseUpdate, session: Session = Depends(get_session)):
    ex = _get(session, ex_id)
    data = body.model_dump(exclude_unset=True)
    if "raw_text" in data and set(data) <= {"raw_text", "reviewed"}:
        # Editing only the raw block re-derives the structured fields.
        ex.raw_text = data["raw_text"]
        _apply_reparse(ex)
    for key, value in data.items():
        if key == "correction" and value is not None and "correction_source" not in data:
            ex.correction_source = ex.correction_source if ex.correction_source != "none" else "booklet"
        if key == "correction" and not value:
            ex.correction_source = "none"
            value = None
        if key == "topic_tags" and value is not None:
            value = [t.strip().lower() for t in value if t.strip()]
        setattr(ex, key, value)
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


def _apply_reparse(ex: BookletExercise) -> None:
    fields = reparse_block(ex.raw_text)
    ex.label = fields["label"]
    ex.statement = fields["statement"]
    ex.given_data = fields["given_data"]
    ex.sub_questions = fields["sub_questions"]
    if fields["correction"]:
        ex.correction = fields["correction"]
        ex.correction_source = "booklet"


def _shift_positions(session: Session, document_id: int, after: int, by: int) -> None:
    for e in session.exec(select(BookletExercise).where(
            BookletExercise.document_id == document_id, BookletExercise.position > after)).all():
        e.position += by
        session.add(e)


@router.post("/{ex_id}/split")
def split_exercise(ex_id: int, body: SplitRequest, session: Session = Depends(get_session)):
    ex = _get(session, ex_id)
    raw = ex.raw_text or ex.statement
    if not (0 < body.offset < len(raw)):
        raise HTTPException(400, "Split position must be inside the text")
    first, second = raw[: body.offset].strip(), raw[body.offset:].strip()
    if not first or not second:
        raise HTTPException(400, "Both parts must contain text")
    _shift_positions(session, ex.document_id, ex.position, 1)
    ex.raw_text = first
    ex.correction, ex.correction_source = None, "none"
    _apply_reparse(ex)
    new = BookletExercise(document_id=ex.document_id, course_id=ex.course_id, chapter_id=ex.chapter_id,
                          label="", position=ex.position + 1, raw_text=second,
                          page_start=ex.page_start, page_end=ex.page_end)
    _apply_reparse(new)
    session.add(ex)
    session.add(new)
    session.commit()
    return {"ok": True, "ids": [ex.id, new.id]}


@router.post("/{ex_id}/merge-next")
def merge_next(ex_id: int, session: Session = Depends(get_session)):
    ex = _get(session, ex_id)
    nxt = session.exec(select(BookletExercise).where(
        BookletExercise.document_id == ex.document_id, BookletExercise.position > ex.position
    ).order_by(BookletExercise.position)).first()
    if not nxt:
        raise HTTPException(400, "No following exercise to merge with")
    ex.raw_text = f"{ex.raw_text}\n\n{nxt.raw_text}".strip()
    existing_correction = ex.correction or nxt.correction
    _apply_reparse(ex)
    if not ex.correction and existing_correction:
        ex.correction, ex.correction_source = existing_correction, "booklet"
    ex.page_end = max(ex.page_end, nxt.page_end)
    for a in session.exec(select(Attempt).where(Attempt.exercise_id == nxt.id)).all():
        a.exercise_id = ex.id
        session.add(a)
    session.delete(nxt)
    session.add(ex)
    session.commit()
    return {"ok": True}


@router.post("")
def create_exercise(body: dict, session: Session = Depends(get_session)):
    doc = session.get(Document, body.get("document_id"))
    if not doc:
        raise HTTPException(400, "document_id is required")
    after = body.get("after_position", -1)
    _shift_positions(session, doc.id, after, 1)
    ex = BookletExercise(document_id=doc.id, course_id=doc.course_id, chapter_id=doc.chapter_id,
                         label=body.get("label") or "Nouvel exercice", position=after + 1,
                         raw_text=body.get("raw_text", ""), statement=body.get("statement", ""))
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


@router.delete("/{ex_id}")
def delete_exercise(ex_id: int, session: Session = Depends(get_session)):
    session.delete(_get(session, ex_id))
    session.commit()
    return {"ok": True}


def _context(session: Session, ex: BookletExercise) -> tuple[str, str]:
    course = session.get(Course, ex.course_id)
    query = f"{ex.statement} {' '.join(q.get('text', '') for q in ex.sub_questions)} {' '.join(ex.topic_tags)}"
    chunks = [c for c in retrieval.search_chunks(session, ex.course_id, query, ex.chapter_id, limit=8)
              if c.document_id != ex.document_id]
    names = {d.id: d.filename for d in session.exec(select(Document).where(Document.course_id == ex.course_id))}
    return course.name, prompts.format_chunks(chunks[:6], names)


def guess_language(text: str) -> str:
    words = set(retrieval.fold(text).split())
    fr = len(words & {"le", "la", "les", "des", "est", "une", "on", "calculer", "determiner", "du", "dans"})
    en = len(words & {"the", "is", "of", "and", "calculate", "determine", "find", "in", "a", "an"})
    return "en" if en > fr else "fr"


@router.post("/{ex_id}/solve")
def solve_exercise(ex_id: int, session: Session = Depends(get_session)):
    ex = _get(session, ex_id)
    if ex.correction and ex.correction_source == "booklet":
        raise HTTPException(400, "This exercise already has a correction from the booklet")
    course_name, excerpts = _context(session, ex)
    language = guess_language(ex.statement)
    try:
        sol = llm.solve(prompts.solve_prompt(course=course_name, exercise=ex, excerpts=excerpts, language=language))
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    parts = []
    for s in sol.solution_steps:
        parts.append(f"**{s.title}**\n\n{s.content}")
    parts.append(f"**{'Réponse' if language == 'fr' else 'Answer'}** : {sol.answer}")
    if sol.assumptions:
        parts.append(f"*{'Hypothèses' if language == 'fr' else 'Assumptions'} : {sol.assumptions}*")
    parts.append(f"*Self-check ({sol.confidence} confidence): {sol.self_check}*")
    ex.correction = "\n\n".join(parts)
    ex.correction_source = "ai"
    if not ex.topic_tags:
        ex.topic_tags = [t.strip().lower() for t in sol.topic_tags if t.strip()][:3]
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


@router.post("/{ex_id}/transcribe")
def transcribe_exercise(ex_id: int, session: Session = Depends(get_session)):
    """Re-read the exercise from page images with Claude vision, to recover equations lost in extraction/OCR."""
    ex = _get(session, ex_id)
    doc = session.get(Document, ex.document_id)
    last = min(ex.page_end, ex.page_start + 3)
    content: list = [llm.image_block(extraction.render_page_png(doc.stored_path, p, dpi=150))
                     for p in range(ex.page_start, last + 1)]
    content.append({"type": "text", "text": prompts.TRANSCRIBE_PROMPT.format(
        label=ex.label, raw=(ex.raw_text or ex.statement)[:6000])})
    try:
        t = llm.call_structured(content, ExerciseTranscription,
                                system="You transcribe engineering exercises from scanned pages into Markdown + LaTeX.")
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    ex.statement = t.statement
    ex.given_data = t.given_data
    ex.sub_questions = [q.model_dump() for q in t.sub_questions]
    if t.correction.strip() and ex.correction_source != "ai":
        ex.correction, ex.correction_source = t.correction, "booklet"
    session.add(ex)
    session.commit()
    session.refresh(ex)
    return ex


@router.post("/tag")
def tag_exercises(body: dict, session: Session = Depends(get_session)):
    """Ask Claude for topic tags on every untagged exercise of a document (or course)."""
    stmt = select(BookletExercise)
    if body.get("document_id"):
        stmt = stmt.where(BookletExercise.document_id == body["document_id"])
    elif body.get("course_id"):
        stmt = stmt.where(BookletExercise.course_id == body["course_id"])
    else:
        raise HTTPException(400, "document_id or course_id is required")
    targets = [e for e in session.exec(stmt).all() if body.get("overwrite") or not e.topic_tags]
    if not targets:
        return {"tagged": 0}
    course = session.get(Course, targets[0].course_id)
    chapters = {c.id: c.name for c in session.exec(select(Chapter).where(Chapter.course_id == course.id))}
    tagged = 0
    for i in range(0, len(targets), 25):
        batch = targets[i:i + 25]
        try:
            result = llm.call_structured(
                prompts.tagging_prompt(course=course.name, chapter_names=chapters, exercises=batch), TagBatch,
                system="You label engineering exercises with concise topic tags.", max_tokens=16000)
        except llm.LLMError as exc:
            raise HTTPException(502, str(exc)) from exc
        by_id = {e.id: e for e in batch}
        for item in result.items:
            if item.exercise_id in by_id:
                by_id[item.exercise_id].topic_tags = [t.strip().lower() for t in item.topic_tags if t.strip()][:3]
                session.add(by_id[item.exercise_id])
                tagged += 1
    session.commit()
    return {"tagged": tagged}
