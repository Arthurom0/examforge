"""Problem generation: standard, weak-spot, and booklet-exercise variants."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Attempt, BookletExercise, Chapter, Course, Document, Problem, ProblemSet
from ..schemas import GeneratedProblem, GenerateRequest, VariantRequest
from ..services import llm, prompts, retrieval, stats
from .exercises import guess_language

router = APIRouter(prefix="/api", tags=["generation"])


def _doc_names(session: Session, course_id: int) -> dict[int, str]:
    return {d.id: d.filename for d in session.exec(select(Document).where(Document.course_id == course_id))}


def _save_set(session: Session, problem_set: ProblemSet, problems: list[GeneratedProblem], language: str) -> dict:
    session.add(problem_set)
    session.flush()
    for i, p in enumerate(problems):
        session.add(Problem(
            set_id=problem_set.id, course_id=problem_set.course_id, chapter_id=problem_set.chapter_id,
            position=i, type=p.type, difficulty=p.difficulty, language=language, title=p.title,
            statement=p.statement, given_data=[g.model_dump() for g in p.given_data],
            choices=[c.model_dump() for c in p.choices], answer=p.answer,
            solution_steps=[s.model_dump() for s in p.solution_steps], topic_tags=p.topic_tags,
            self_check=p.self_check,
        ))
    session.commit()
    return get_set(problem_set.id, session)


@router.post("/generate")
def generate(body: GenerateRequest, session: Session = Depends(get_session)):
    course = session.get(Course, body.course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    chapter = session.get(Chapter, body.chapter_id) if body.chapter_id else None

    focus_topics: list[str] = []
    if body.weak_spot:
        weak = stats.weak_topics(session, course.id, chapter.id if chapter else None, k=3)
        focus_topics = [w["topic"] for w in weak]

    query = " ".join(filter(None, [chapter.name if chapter else course.name, " ".join(focus_topics), body.focus]))
    chunks = retrieval.search_chunks(session, course.id, query, chapter.id if chapter else None, limit=10)
    references = retrieval.similar_exercises(session, course.id, query, chapter.id if chapter else None, limit=3)

    prompt = prompts.generation_prompt(
        course=course.name, chapter=chapter.name if chapter else None,
        excerpts=prompts.format_chunks(chunks, _doc_names(session, course.id)),
        references=prompts.format_reference_exercises(references), count=body.count, types=body.types,
        difficulty=body.difficulty, language=body.language, focus_topics=focus_topics, user_focus=body.focus,
    )
    try:
        problems = llm.generate_validated(prompt, body.count, body.types)
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    mode = "weak_spot" if body.weak_spot else "standard"
    title = f"{chapter.name if chapter else course.name} · {body.difficulty}"
    if focus_topics:
        title += " · " + ", ".join(focus_topics)
    params = body.model_dump() | {"focus_topics": focus_topics, "retrieved_chunks": [c.id for c in chunks],
                                  "reference_exercises": [e.id for e in references]}
    ps = ProblemSet(course_id=course.id, chapter_id=chapter.id if chapter else None, mode=mode,
                    params=params, title=title)
    return _save_set(session, ps, problems, body.language)


@router.post("/exercises/{ex_id}/variants")
def generate_variants(ex_id: int, body: VariantRequest, session: Session = Depends(get_session)):
    ex = session.get(BookletExercise, ex_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    course = session.get(Course, ex.course_id)
    language = body.language or guess_language(ex.statement)
    query = f"{ex.statement} {' '.join(q.get('text', '') for q in ex.sub_questions)}"
    chunks = [c for c in retrieval.search_chunks(session, course.id, query, ex.chapter_id, limit=8)
              if c.document_id != ex.document_id][:6]
    prompt = prompts.variant_prompt(course=course.name, exercise=ex,
                                    excerpts=prompts.format_chunks(chunks, _doc_names(session, course.id)),
                                    count=body.count, kinds=body.kinds, language=language)
    try:
        problems = llm.generate_validated(prompt, body.count, None)
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    for p in problems:
        if ex.topic_tags:
            p.topic_tags = list(dict.fromkeys(ex.topic_tags + p.topic_tags))[:3]
    ps = ProblemSet(course_id=course.id, chapter_id=ex.chapter_id, mode="variant", source_exercise_id=ex.id,
                    params=body.model_dump() | {"language": language}, title=f"Variantes · {ex.label}")
    return _save_set(session, ps, problems, language)


@router.get("/sets")
def list_sets(course_id: int | None = None, session: Session = Depends(get_session)):
    stmt = select(ProblemSet).order_by(ProblemSet.created_at.desc())
    if course_id is not None:
        stmt = stmt.where(ProblemSet.course_id == course_id)
    sets = session.exec(stmt).all()
    out = []
    for s in sets:
        problems = session.exec(select(Problem).where(Problem.set_id == s.id)).all()
        ids = [p.id for p in problems]
        attempted = {a.problem_id for a in session.exec(select(Attempt).where(Attempt.problem_id.in_(ids)))} if ids else set()
        out.append({**s.model_dump(), "problem_count": len(problems), "attempted": len(attempted)})
    return out


@router.get("/sets/{set_id}")
def get_set(set_id: int, session: Session = Depends(get_session)):
    ps = session.get(ProblemSet, set_id)
    if not ps:
        raise HTTPException(404, "Problem set not found")
    problems = session.exec(select(Problem).where(Problem.set_id == set_id).order_by(Problem.position)).all()
    ids = [p.id for p in problems]
    attempts = session.exec(select(Attempt).where(Attempt.problem_id.in_(ids)).order_by(Attempt.created_at)).all() if ids else []
    last = {a.problem_id: a.result for a in attempts}
    course = session.get(Course, ps.course_id)
    chapter = session.get(Chapter, ps.chapter_id) if ps.chapter_id else None
    source = session.get(BookletExercise, ps.source_exercise_id) if ps.source_exercise_id else None
    return {
        **ps.model_dump(),
        "course_name": course.name if course else "",
        "chapter_name": chapter.name if chapter else None,
        "source_exercise": source.model_dump() if source else None,
        "problems": [{**p.model_dump(), "last_result": last.get(p.id)} for p in problems],
    }


@router.delete("/sets/{set_id}")
def delete_set(set_id: int, session: Session = Depends(get_session)):
    ps = session.get(ProblemSet, set_id)
    if not ps:
        raise HTTPException(404, "Problem set not found")
    session.delete(ps)
    session.commit()
    return {"ok": True}
