"""Split a tutorial booklet (fascicule de TD) into exercises.

Handles the common layouts:
  * "Exercice 1", "Exercice n°2", "Ex. 3", "EXERCICE IV", "Exercise 5", "Problème 2"
  * a correction right after each exercise ("Correction", "Corrigé", "Solution", "Réponses")
  * a separate corrections section at the end that repeats the exercise labels
  * chapter headings ("Chapitre 3 : ...", "TD 2 - ...") when one booklet spans several chapters
  * sub-questions "1)", "2.", "a)", "(b)", "Q3"
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extraction import PageText

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
         "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15}

EXERCISE_RE = re.compile(
    r"^[ \t]*(?P<head>(?:exercices?|exercises?|exo|ex\.?|probl[eè]mes?|problems?)"
    r"[ \t]*(?:n[°o]\.?[ \t]*)?(?P<num>\d{1,3}|[IVX]{1,5})\b(?:[ \t]*[:.\-–—)][^\n]*|[ \t]+[^\n]{0,80})?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
CHAPTER_RE = re.compile(
    r"^[ \t]*(?:chapitre|chapter|td|s[ée]ance|partie|part)[ \t]*(?:n[°o]\.?[ \t]*)?(?P<num>\d{1,2}|[IVX]{1,4})"
    r"[ \t]*[:.\-–—]?[ \t]*(?P<title>[^\n]{0,90})$",
    re.IGNORECASE | re.MULTILINE,
)
CORRECTION_SECTION_RE = re.compile(
    # Plural forms only: a singular "Correction" right after an exercise is an inline correction.
    r"^[ \t]*(?:corrig[ée]s|corrections|solutions|corrig[ée][ \t]+des[ \t]+exercices|"
    r"[ée]l[ée]ments de (?:r[ée]ponses|correction))(?:[ \t]+des[ \t]+exercices)?[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
INLINE_CORRECTION_RE = re.compile(
    r"^[ \t]*(?:correction|corrig[ée]|solution|r[ée]ponses?|answers?|[ée]l[ée]ments de r[ée]ponse)\b[^\n]{0,40}$",
    re.IGNORECASE | re.MULTILINE,
)
SUBQ_RE = re.compile(
    r"^[ \t]*(?P<label>\d{1,2}[.)]|[a-h][.)]|\([a-h]\)|\(\d{1,2}\)|Q\d{1,2}[.):]?)[ \t]+(?=\S)",
    re.MULTILINE,
)
GIVEN_HEAD_RE = re.compile(
    r"^[ \t]*(?:donn[ée]es(?:[ \t]+num[ée]riques)?|on donne|data|given|valeurs num[ée]riques)[ \t]*:?",
    re.IGNORECASE | re.MULTILINE,
)
ASSIGNMENT_RE = re.compile(r"[A-Za-zα-ωΑ-Ω_][\w₀-₉]*\s*=\s*[-−]?\d[\d.,]*\s*(?:[×x]\s*10\^?[-−]?\d+)?\s*[^\s,;]*")


@dataclass
class ParsedExercise:
    label: str
    number: int | None
    raw_text: str
    statement: str
    given_data: str
    sub_questions: list[dict]
    correction: str | None
    page_start: int
    page_end: int
    chapter_title: str | None = None
    extra: dict = field(default_factory=dict)


def _num(token: str) -> int | None:
    token = token.upper()
    if token.isdigit():
        return int(token)
    return ROMAN.get(token)


def _join_pages(pages: list[PageText]) -> tuple[str, list[tuple[int, int]]]:
    """Concatenate pages; return text and a list of (offset, page_number)."""
    parts, offsets, pos = [], [], 0
    for p in pages:
        offsets.append((pos, p.page))
        parts.append(p.text)
        pos += len(p.text) + 2
    return "\n\n".join(parts), offsets


def _page_at(offsets: list[tuple[int, int]], index: int) -> int:
    page = offsets[0][1] if offsets else 1
    for off, num in offsets:
        if off <= index:
            page = num
        else:
            break
    return page


def split_fields(raw: str) -> tuple[str, str, list[dict], str | None]:
    """From one exercise block (header line removed), extract statement, given data, sub-questions, correction."""
    correction = None
    m = INLINE_CORRECTION_RE.search(raw)
    if m and m.start() > 0:
        correction = raw[m.end():].strip() or None
        raw = raw[: m.start()]

    sub_questions: list[dict] = []
    matches = list(SUBQ_RE.finditer(raw))
    # Only treat it as a sub-question list if labels look sequential-ish (avoid "1. " inside prose).
    if len(matches) >= 2:
        intro = raw[: matches[0].start()].strip()
        for i, sm in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
            label = sm.group("label").strip("().:")
            sub_questions.append({"label": label, "text": raw[sm.end():end].strip()})
    else:
        intro = raw.strip()

    given = ""
    gm = GIVEN_HEAD_RE.search(intro)
    if gm:
        tail = intro[gm.start():]
        para_end = tail.find("\n\n")
        given = (tail if para_end == -1 else tail[:para_end]).strip()
    else:
        assigns = ASSIGNMENT_RE.findall(intro)
        if len(assigns) >= 2:
            given = "; ".join(a.strip() for a in assigns)
    return intro, given, sub_questions, correction


def parse_booklet(pages: list[PageText]) -> list[ParsedExercise]:
    text, offsets = _join_pages(pages)
    if not text.strip():
        return []

    chapters = [(m.start(), m.group(0).strip()) for m in CHAPTER_RE.finditer(text)]

    def chapter_at(index: int) -> str | None:
        title = None
        for off, t in chapters:
            if off <= index:
                title = t
        return title

    corr_section = CORRECTION_SECTION_RE.search(text)
    corr_start = corr_section.start() if corr_section else None
    # A "Corrections" heading in the first 5% of the doc is probably a table of contents entry.
    if corr_start is not None and corr_start < len(text) * 0.05:
        corr_start = None

    headers = list(EXERCISE_RE.finditer(text))
    if not headers:
        intro, given, subs, corr = split_fields(text)
        return [ParsedExercise(
            label="Exercice 1", number=1, raw_text=text, statement=intro, given_data=given,
            sub_questions=subs, correction=corr, page_start=pages[0].page, page_end=pages[-1].page,
            extra={"no_headers": True},
        )]

    blocks = []
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        if corr_start is not None and h.start() < corr_start < end:
            end = corr_start
        # A chapter heading between two exercises belongs to neither.
        for off, _ in chapters:
            if h.end() < off < end:
                end = off
                break
        blocks.append((h, end))

    exercises: list[ParsedExercise] = []
    corrections_by_num: dict[int, str] = {}
    for h, end in blocks:
        body = text[h.end():end].strip()
        number = _num(h.group("num"))
        in_corrections = corr_start is not None and h.start() > corr_start
        seen_numbers = {e.number for e in exercises}
        if in_corrections or (number is not None and number in seen_numbers and exercises):
            if number is not None:
                corrections_by_num[number] = (corrections_by_num.get(number, "") + "\n" + body).strip()
            continue
        intro, given, subs, corr = split_fields(body)
        exercises.append(ParsedExercise(
            label=h.group("head").strip()[:120],
            number=number,
            raw_text=text[h.start():end].strip(),
            statement=intro,
            given_data=given,
            sub_questions=subs,
            correction=corr,
            page_start=_page_at(offsets, h.start()),
            page_end=_page_at(offsets, max(h.start(), end - 1)),
            chapter_title=chapter_at(h.start()),
        ))

    for ex in exercises:
        if ex.correction is None and ex.number in corrections_by_num:
            ex.correction = corrections_by_num[ex.number]
    return exercises


def reparse_block(raw_text: str) -> dict:
    """Re-derive fields after a manual split/merge. The first line is kept as the label if it is a header."""
    raw_text = raw_text.strip()
    m = EXERCISE_RE.match(raw_text)
    if m:
        label, body = m.group("head").strip()[:120], raw_text[m.end():]
    else:
        first = raw_text.split("\n", 1)[0]
        label, body = (first[:60] or "Exercice"), raw_text
    intro, given, subs, corr = split_fields(body)
    return {"label": label, "statement": intro, "given_data": given, "sub_questions": subs, "correction": corr}
