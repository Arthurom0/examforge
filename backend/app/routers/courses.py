from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..db import get_session
from ..models import Attempt, BookletExercise, Chapter, Chunk, Course, Document, Problem
from ..schemas import ChapterIn, CourseIn

router = APIRouter(prefix="/api/courses", tags=["courses"])


def get_course(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    return course


def _count(session: Session, model, *conds) -> int:
    return session.exec(select(func.count()).select_from(model).where(*conds)).one()


@router.get("")
def list_courses(session: Session = Depends(get_session)):
    out = []
    for c in session.exec(select(Course).order_by(Course.name)).all():
        chapters = session.exec(
            select(Chapter).where(Chapter.course_id == c.id).order_by(Chapter.position, Chapter.id)
        ).all()
        out.append({
            **c.model_dump(),
            "chapters": [
                {**ch.model_dump(),
                 "documents": _count(session, Document, Document.chapter_id == ch.id),
                 "exercises": _count(session, BookletExercise, BookletExercise.chapter_id == ch.id)}
                for ch in chapters
            ],
            "documents": _count(session, Document, Document.course_id == c.id),
            "exercises": _count(session, BookletExercise, BookletExercise.course_id == c.id),
            "problems": _count(session, Problem, Problem.course_id == c.id),
            "attempts": _count(session, Attempt, Attempt.course_id == c.id),
        })
    return out


@router.post("")
def create_course(body: CourseIn, session: Session = Depends(get_session)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if session.exec(select(Course).where(Course.name == name)).first():
        raise HTTPException(409, "A course with this name already exists")
    course = Course(name=name)
    session.add(course)
    session.commit()
    session.refresh(course)
    return course


@router.patch("/{course_id}")
def rename_course(course_id: int, body: CourseIn, session: Session = Depends(get_session)):
    course = get_course(session, course_id)
    course.name = body.name.strip()
    session.add(course)
    session.commit()
    return course


@router.delete("/{course_id}")
def delete_course(course_id: int, session: Session = Depends(get_session)):
    course = get_course(session, course_id)
    session.delete(course)
    session.commit()
    return {"ok": True}


@router.post("/{course_id}/chapters")
def create_chapter(course_id: int, body: ChapterIn, session: Session = Depends(get_session)):
    get_course(session, course_id)
    position = body.position
    if position is None:
        position = _count(session, Chapter, Chapter.course_id == course_id)
    chapter = Chapter(course_id=course_id, name=body.name.strip(), position=position)
    session.add(chapter)
    session.commit()
    session.refresh(chapter)
    return chapter


@router.patch("/chapters/{chapter_id}")
def update_chapter(chapter_id: int, body: ChapterIn, session: Session = Depends(get_session)):
    chapter = session.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    chapter.name = body.name.strip()
    if body.position is not None:
        chapter.position = body.position
    session.add(chapter)
    session.commit()
    return chapter


@router.delete("/chapters/{chapter_id}")
def delete_chapter(chapter_id: int, session: Session = Depends(get_session)):
    chapter = session.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    # Keep documents and exercises; they just lose their chapter.
    for model in (Chunk, BookletExercise, Problem, Attempt):
        for row in session.exec(select(model).where(model.chapter_id == chapter_id)).all():
            row.chapter_id = None
            session.add(row)
    session.delete(chapter)
    session.commit()
    return {"ok": True}

