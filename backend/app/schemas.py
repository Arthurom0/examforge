"""Pydantic schemas: the JSON contract with Claude, and request bodies for the API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ProblemType = Literal["mcq", "numerical", "derivation", "conceptual"]
Difficulty = Literal["easy", "medium", "exam"]
Language = Literal["fr", "en"]
AttemptResult = Literal["correct", "partial", "wrong"]


# ---------- Claude output contract ----------

class GivenItem(BaseModel):
    symbol: str = Field(description="Symbol in LaTeX, e.g. \\rho or D_h")
    value: str = Field(description="Numerical value as text, e.g. '1.2' or '2.5 \\times 10^{5}'")
    unit: str = Field(description="SI unit in LaTeX, e.g. 'kg\\,m^{-3}'; empty string if dimensionless")
    description: str


class Choice(BaseModel):
    label: str = Field(description="A, B, C, D")
    text: str


class SolutionStep(BaseModel):
    title: str
    content: str = Field(description="Markdown with LaTeX math ($...$ inline, $$...$$ display)")


class GeneratedProblem(BaseModel):
    title: str = Field(description="Short title, a few words")
    type: ProblemType
    difficulty: Difficulty
    statement: str = Field(description="Full problem statement, Markdown + LaTeX")
    given_data: list[GivenItem]
    choices: list[Choice] = Field(description="4 options for mcq, empty list otherwise")
    answer: str = Field(description="Final answer. Numerical: value with unit. MCQ: the correct label and its text")
    solution_steps: list[SolutionStep]
    topic_tags: list[str] = Field(description="1 to 3 short topic tags in the problem's language, lowercase")
    self_check: str = Field(description="What you verified: recomputation, unit/dimension check, order of magnitude")


class ProblemBatch(BaseModel):
    problems: list[GeneratedProblem]


class GeneratedSolution(BaseModel):
    answer: str
    solution_steps: list[SolutionStep]
    topic_tags: list[str]
    self_check: str
    confidence: Literal["high", "medium", "low"]
    assumptions: str = Field(description="Assumptions or ambiguities in the statement; empty if none")


class ExerciseTags(BaseModel):
    exercise_id: int
    topic_tags: list[str]


class TagBatch(BaseModel):
    items: list[ExerciseTags]


class SubQuestion(BaseModel):
    label: str
    text: str


class ExerciseTranscription(BaseModel):
    statement: str
    given_data: str
    sub_questions: list[SubQuestion]
    correction: str = Field(description="Correction text if present on the pages, else empty string")


# ---------- API request bodies ----------

class CourseIn(BaseModel):
    name: str


class ChapterIn(BaseModel):
    name: str
    position: Optional[int] = None


class ExerciseUpdate(BaseModel):
    label: Optional[str] = None
    chapter_id: Optional[int] = None
    statement: Optional[str] = None
    given_data: Optional[str] = None
    sub_questions: Optional[list[dict]] = None
    correction: Optional[str] = None
    correction_source: Optional[Literal["none", "booklet", "ai"]] = None
    topic_tags: Optional[list[str]] = None
    raw_text: Optional[str] = None
    reviewed: Optional[bool] = None


class SplitRequest(BaseModel):
    offset: int = Field(description="Character offset in raw_text where the second exercise starts")


class GenerateRequest(BaseModel):
    course_id: int
    chapter_id: Optional[int] = None
    difficulty: Difficulty = "medium"
    types: list[ProblemType] = ["numerical"]
    language: Language = "fr"
    count: int = Field(default=3, ge=1, le=10)
    weak_spot: bool = False
    focus: Optional[str] = Field(default=None, description="Optional extra topic focus typed by the user")


class VariantRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=6)
    language: Optional[Language] = None
    kinds: list[Literal["values", "reversed", "twist"]] = ["values", "reversed", "twist"]


class AttemptIn(BaseModel):
    result: AttemptResult
    problem_id: Optional[int] = None
    exercise_id: Optional[int] = None
