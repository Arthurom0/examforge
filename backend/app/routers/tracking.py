"""Attempts (correct / partial / wrong) and statistics."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Attempt, BookletExercise, Problem
from ..schemas import AttemptIn
from ..services import stats

router = APIRouter(prefix="/api", tags=["tracking"])


@router.post("/attempts")
def record_attempt(body: AttemptIn, session: Session = Depends(get_session)):
    if (body.problem_id is None) == (body.exercise_id is None):
        raise HTTPException(400, "Give exactly one of problem_id or exercise_id")
    if body.problem_id is not None:
        p = session.get(Problem, body.problem_id)
        if not p:
            raise HTTPException(404, "Problem not found")
        attempt = Attempt(origin="generated", problem_id=p.id, course_id=p.course_id, chapter_id=p.chapter_id,
                          topic_tags=p.topic_tags, result=body.result, score=stats.SCORES[body.result])
    else:
        e = session.get(BookletExercise, body.exercise_id)
        if not e:
            raise HTTPException(404, "Exercise not found")
        attempt = Attempt(origin="booklet", exercise_id=e.id, course_id=e.course_id, chapter_id=e.chapter_id,
                          topic_tags=e.topic_tags, result=body.result, score=stats.SCORES[body.result])
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


@router.get("/attempts")
def list_attempts(course_id: Optional[int] = None, limit: int = 50, session: Session = Depends(get_session)):
    stmt = select(Attempt).order_by(Attempt.created_at.desc()).limit(limit)
    if course_id is not None:
        stmt = stmt.where(Attempt.course_id == course_id)
    return session.exec(stmt).all()


@router.delete("/attempts/{attempt_id}")
def delete_attempt(attempt_id: int, session: Session = Depends(get_session)):
    a = session.get(Attempt, attempt_id)
    if not a:
        raise HTTPException(404, "Attempt not found")
    session.delete(a)
    session.commit()
    return {"ok": True}


@router.get("/stats/overview")
def stats_overview(session: Session = Depends(get_session)):
    return stats.overview(session)


@router.get("/stats/timeline")
def stats_timeline(course_id: Optional[int] = None, chapter_id: Optional[int] = None,
                   origin: Optional[str] = None, granularity: str = "week",
                   session: Session = Depends(get_session)):
    return stats.timeline(session, course_id, chapter_id, origin, granularity)


@router.get("/stats/topics")
def stats_topics(course_id: int, chapter_id: Optional[int] = None, origin: Optional[str] = None,
                 session: Session = Depends(get_session)):
    return stats.topic_stats(session, course_id, chapter_id, origin)


@router.get("/stats/weak-topics")
def stats_weak(course_id: int, chapter_id: Optional[int] = None, session: Session = Depends(get_session)):
    return stats.weak_topics(session, course_id, chapter_id, k=5)
