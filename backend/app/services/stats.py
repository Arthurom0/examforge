"""Performance statistics and weak-spot topic selection."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..models import Attempt, Chapter, Course

SCORES = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}
# Bayesian smoothing toward 50%: a topic needs a few attempts before it looks very weak or very strong.
PRIOR_WEIGHT = 2.0
PRIOR_MEAN = 0.5


def smoothed(total: float, n: int) -> float:
    return (total + PRIOR_WEIGHT * PRIOR_MEAN) / (n + PRIOR_WEIGHT)


def _agg(attempts: list[Attempt]) -> dict:
    n = len(attempts)
    total = sum(a.score for a in attempts)
    by_result = {k: sum(1 for a in attempts if a.result == k) for k in SCORES}
    return {"attempts": n, "success_rate": round(total / n, 3) if n else None, **by_result}


def _attempts(session: Session, course_id: int | None = None, chapter_id: int | None = None,
              origin: str | None = None) -> list[Attempt]:
    stmt = select(Attempt)
    if course_id is not None:
        stmt = stmt.where(Attempt.course_id == course_id)
    if chapter_id is not None:
        stmt = stmt.where(Attempt.chapter_id == chapter_id)
    if origin:
        stmt = stmt.where(Attempt.origin == origin)
    return list(session.exec(stmt.order_by(Attempt.created_at)).all())


def overview(session: Session) -> list[dict]:
    courses = session.exec(select(Course).order_by(Course.name)).all()
    chapters = session.exec(select(Chapter).order_by(Chapter.position, Chapter.id)).all()
    attempts = _attempts(session)
    by_course, by_chapter = defaultdict(list), defaultdict(list)
    for a in attempts:
        by_course[a.course_id].append(a)
        by_chapter[(a.course_id, a.chapter_id)].append(a)
    out = []
    for c in courses:
        ca = by_course[c.id]
        chapter_rows = []
        for ch in [x for x in chapters if x.course_id == c.id]:
            cha = by_chapter[(c.id, ch.id)]
            chapter_rows.append({
                "chapter_id": ch.id, "name": ch.name, **_agg(cha),
                "generated": _agg([a for a in cha if a.origin == "generated"]),
                "booklet": _agg([a for a in cha if a.origin == "booklet"]),
            })
        unassigned = by_chapter[(c.id, None)]
        if unassigned:
            chapter_rows.append({"chapter_id": None, "name": "(no chapter)", **_agg(unassigned),
                                 "generated": _agg([a for a in unassigned if a.origin == "generated"]),
                                 "booklet": _agg([a for a in unassigned if a.origin == "booklet"])})
        out.append({
            "course_id": c.id, "name": c.name, **_agg(ca),
            "generated": _agg([a for a in ca if a.origin == "generated"]),
            "booklet": _agg([a for a in ca if a.origin == "booklet"]),
            "chapters": chapter_rows,
        })
    return out


def _period(dt: datetime, granularity: str) -> str:
    if granularity == "day":
        return dt.strftime("%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")


def timeline(session: Session, course_id: int | None = None, chapter_id: int | None = None,
             origin: str | None = None, granularity: str = "week") -> dict:
    """Success rate per period, overall and per course (or per chapter when a course is selected)."""
    attempts = _attempts(session, course_id, chapter_id, origin)
    series: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    names: dict[str, str] = {}
    if course_id is None:
        for c in session.exec(select(Course)).all():
            names[f"course:{c.id}"] = c.name
    else:
        for ch in session.exec(select(Chapter).where(Chapter.course_id == course_id)).all():
            names[f"chapter:{ch.id}"] = ch.name
        names["chapter:None"] = "(no chapter)"
    periods = set()
    for a in attempts:
        p = _period(a.created_at, granularity)
        periods.add(p)
        series["all"][p].append(a.score)
        key = f"course:{a.course_id}" if course_id is None else f"chapter:{a.chapter_id}"
        series[key][p].append(a.score)
    ordered = sorted(periods)
    names["all"] = "All"
    return {
        "periods": ordered,
        "series": [
            {"key": key, "name": names.get(key, key),
             "points": [{"period": p, "attempts": len(v), "success_rate": round(sum(v) / len(v), 3)}
                        for p in ordered if (v := pts.get(p))]}
            for key, pts in series.items()
        ],
    }


def topic_stats(session: Session, course_id: int, chapter_id: int | None = None,
                origin: str | None = None) -> list[dict]:
    totals: dict[str, list[float]] = defaultdict(list)
    for a in _attempts(session, course_id, chapter_id, origin):
        for t in a.topic_tags or []:
            totals[t.strip().lower()].append(a.score)
    rows = [{"topic": t, "attempts": len(v), "success_rate": round(sum(v) / len(v), 3),
             "smoothed": round(smoothed(sum(v), len(v)), 3)} for t, v in totals.items() if t]
    rows.sort(key=lambda r: (r["smoothed"], -r["attempts"]))
    return rows


def weak_topics(session: Session, course_id: int, chapter_id: int | None = None, k: int = 3) -> list[dict]:
    """Lowest smoothed success rate first. Topics already mastered (>= 85%) are excluded."""
    rows = topic_stats(session, course_id, chapter_id)
    if not rows and chapter_id is not None:
        rows = topic_stats(session, course_id)  # fall back to the whole course
    return [r for r in rows if r["smoothed"] < 0.85][:k]
