"""BM25 keyword retrieval over stored chunks. Accent-insensitive, FR + EN stopwords, light stemming."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from sqlmodel import Session, select

from ..models import BookletExercise, Chunk

STOPWORDS = set("""
le la les un une des du de d l au aux et ou en dans par pour sur avec sans sous ce cette ces cet est sont
etre a ont avoir il elle ils elles on nous vous je tu se sa son ses leur leurs qui que quoi dont ou
ne pas plus moins tres tout tous toute toutes comme si mais donc or ni car y alors ainsi entre vers chez
the of and or in on at to for with without by from is are be been was were this that these those an as it
its their there which who what when where how than then into over under also can may such each per
soit soient on donne calculer determiner montrer exprimer question exercice exercise
""".split())


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def stem(token: str) -> str:
    for suffix in ("ements", "ement", "ations", "ation", "ions", "ion", "ites", "ite", "eurs", "eur",
                   "iques", "ique", "ives", "ive", "ing", "ies", "es", "s", "x"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", fold(text))
    return [stem(t) for t in tokens if len(t) > 1 and t not in STOPWORDS]


def bm25_rank(query: str, docs: list[str], k1: float = 1.4, b: float = 0.75) -> list[float]:
    q_terms = set(tokenize(query))
    if not docs or not q_terms:
        return [0.0] * len(docs)
    tokenized = [tokenize(d) for d in docs]
    avgdl = sum(len(t) for t in tokenized) / len(tokenized) or 1.0
    df = Counter()
    for toks in tokenized:
        df.update(set(toks) & q_terms)
    n = len(docs)
    scores = []
    for toks in tokenized:
        tf = Counter(t for t in toks if t in q_terms)
        dl = len(toks) or 1
        s = 0.0
        for term, f in tf.items():
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


def search_chunks(session: Session, course_id: int, query: str, chapter_id: int | None = None,
                  limit: int = 8, chapter_boost: float = 1.5) -> list[Chunk]:
    chunks = session.exec(select(Chunk).where(Chunk.course_id == course_id)).all()
    if not chunks:
        return []
    scores = bm25_rank(query, [c.text for c in chunks])
    ranked = []
    for c, s in zip(chunks, scores):
        if chapter_id is not None and c.chapter_id == chapter_id:
            s = s * chapter_boost + 0.5  # keep chapter material even when the query is vague
        ranked.append((s, c))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [c for s, c in ranked[:limit] if s > 0]


def similar_exercises(session: Session, course_id: int, query: str, chapter_id: int | None = None,
                      limit: int = 3, exclude_id: int | None = None) -> list[BookletExercise]:
    stmt = select(BookletExercise).where(BookletExercise.course_id == course_id)
    exercises = [e for e in session.exec(stmt).all() if e.id != exclude_id and e.statement.strip()]
    if not exercises:
        return []
    docs = [f"{e.label} {e.statement} {' '.join(e.topic_tags)} "
            f"{' '.join(q.get('text', '') for q in e.sub_questions)}" for e in exercises]
    scores = bm25_rank(query, docs)
    ranked = []
    for e, s in zip(exercises, scores):
        if chapter_id is not None and e.chapter_id == chapter_id:
            s = s * 1.5 + 1.0
        ranked.append((s, e))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in ranked[:limit]]
