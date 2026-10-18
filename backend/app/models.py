"""Database tables. JSON columns hold small lists/dicts (tags, steps, given data)."""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, ForeignKey, Integer
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fk(target: str, nullable: bool = True, ondelete: str = "CASCADE") -> Any:
    return Field(
        default=None,
        sa_column=Column(Integer, ForeignKey(target, ondelete=ondelete), nullable=nullable, index=True),
    )


def _json(default_factory=list) -> Any:
    return Field(default_factory=default_factory, sa_column=Column(JSON, nullable=False))


class Course(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow)


class Chapter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True))
    name: str
    position: int = 0


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True))
    chapter_id: Optional[int] = _fk("chapter.id", ondelete="SET NULL")
    kind: str = "lecture"  # lecture | exam | booklet
    filename: str
    stored_path: str
    page_count: int = 0
    ocr_used: bool = False
    ocr_pages: int = 0
    status: str = "pending"  # pending | ready | error
    error: Optional[str] = None
    char_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class Chunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(sa_column=Column(Integer, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True))
    course_id: int = Field(index=True)
    chapter_id: Optional[int] = Field(default=None, index=True)
    page: int
    text: str


class BookletExercise(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(sa_column=Column(Integer, ForeignKey("document.id", ondelete="CASCADE"), nullable=False, index=True))
    course_id: int = Field(index=True)
    chapter_id: Optional[int] = Field(default=None, index=True)
    label: str
    position: int = 0
    raw_text: str = ""  # the parser's text block; split/merge operate on this
    statement: str = ""
    given_data: str = ""
    sub_questions: list = _json()  # [{"label": "a", "text": "..."}]
    correction: Optional[str] = None
    correction_source: str = "none"  # none | booklet | ai
    page_start: int = 1
    page_end: int = 1
    topic_tags: list = _json()
    reviewed: bool = False


class ProblemSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True))
    chapter_id: Optional[int] = _fk("chapter.id", ondelete="SET NULL")
    mode: str = "standard"  # standard | weak_spot | variant
    params: dict = _json(dict)
    source_exercise_id: Optional[int] = _fk("bookletexercise.id", ondelete="SET NULL")
    title: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Problem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    set_id: int = Field(sa_column=Column(Integer, ForeignKey("problemset.id", ondelete="CASCADE"), nullable=False, index=True))
    course_id: int = Field(index=True)
    chapter_id: Optional[int] = Field(default=None, index=True)
    position: int = 0
    type: str  # mcq | numerical | derivation | conceptual
    difficulty: str  # easy | medium | exam
    language: str  # fr | en
    title: str = ""
    statement: str
    given_data: list = _json()  # [{"symbol","value","unit","description"}]
    choices: list = _json()  # MCQ only: [{"label":"A","text":"..."}]
    answer: str
    solution_steps: list = _json()  # [{"title","content"}]
    topic_tags: list = _json()
    self_check: str = ""


class Attempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str  # generated | booklet
    problem_id: Optional[int] = _fk("problem.id")
    # SET NULL: re-extracting a booklet recreates its exercises but keeps your history in the stats.
    exercise_id: Optional[int] = _fk("bookletexercise.id", ondelete="SET NULL")
    course_id: int = Field(sa_column=Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False, index=True))
    chapter_id: Optional[int] = Field(default=None, index=True)
    topic_tags: list = _json()
    result: str  # correct | partial | wrong
    score: float
    created_at: datetime = Field(default_factory=utcnow, index=True)
