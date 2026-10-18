import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, delete, select

from ..config import settings
from ..db import engine, get_session
from ..models import BookletExercise, Chapter, Chunk, Document
from ..services import booklet_parser, extraction
from .courses import get_course

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

KINDS = {"lecture", "exam", "booklet"}


@router.get("")
def list_documents(course_id: Optional[int] = None, session: Session = Depends(get_session)):
    stmt = select(Document).order_by(Document.created_at.desc())
    if course_id is not None:
        stmt = stmt.where(Document.course_id == course_id)
    return session.exec(stmt).all()


@router.post("")
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    course_id: int = Form(...),
    kind: str = Form("lecture"),
    chapter_id: Optional[int] = Form(None),
    session: Session = Depends(get_session),
):
    get_course(session, course_id)
    if kind not in KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(KINDS)}")
    if chapter_id is not None:
        ch = session.get(Chapter, chapter_id)
        if not ch or ch.course_id != course_id:
            raise HTTPException(400, "Chapter does not belong to this course")
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are supported")
    safe = re.sub(r"[^\w.\-]+", "_", file.filename or "document.pdf")
    stored = settings.upload_dir / f"{uuid.uuid4().hex[:10]}_{safe}"
    stored.write_bytes(data)
    doc = Document(course_id=course_id, chapter_id=chapter_id, kind=kind,
                   filename=file.filename or safe, stored_path=str(stored))
    session.add(doc)
    session.commit()
    session.refresh(doc)
    background.add_task(process_document, doc.id)
    return doc


@router.get("/{doc_id}")
def get_document(doc_id: int, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    chunks = session.exec(select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.page, Chunk.id)).all()
    return {**doc.model_dump(), "chunks": len(chunks),
            "preview": [{"page": c.page, "text": c.text[:400]} for c in chunks[:5]]}


@router.get("/{doc_id}/text")
def document_text(doc_id: int, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    pages = extraction.extract_pdf(doc.stored_path)
    return [{"page": p.page, "ocr": p.ocr, "text": p.text} for p in pages]


@router.get("/{doc_id}/file")
def document_file(doc_id: int, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    return FileResponse(doc.stored_path, media_type="application/pdf", filename=doc.filename)


@router.get("/{doc_id}/pages/{page}.png")
def page_image(doc_id: int, page: int, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    if page < 1 or page > doc.page_count:
        raise HTTPException(404, "Page out of range")
    return Response(extraction.render_page_png(doc.stored_path, page, dpi=110), media_type="image/png")


@router.patch("/{doc_id}")
def update_document(doc_id: int, body: dict, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    if "chapter_id" in body:
        doc.chapter_id = body["chapter_id"]
        for model in (Chunk, BookletExercise):
            for row in session.exec(select(model).where(model.document_id == doc_id)).all():
                row.chapter_id = doc.chapter_id
                session.add(row)
    if "kind" in body and body["kind"] in KINDS:
        doc.kind = body["kind"]
    session.add(doc)
    session.commit()
    return doc


@router.post("/{doc_id}/reprocess")
def reprocess(doc_id: int, background: BackgroundTasks, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    doc.status = "pending"
    session.add(doc)
    session.commit()
    background.add_task(process_document, doc_id)
    return {"ok": True}


@router.delete("/{doc_id}")
def delete_document(doc_id: int, session: Session = Depends(get_session)):
    doc = _get(session, doc_id)
    Path(doc.stored_path).unlink(missing_ok=True)
    session.delete(doc)
    session.commit()
    return {"ok": True}


def _get(session: Session, doc_id: int) -> Document:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


def process_document(doc_id: int) -> None:
    """Extract text, store chunks, and for booklets split into exercises. Runs in the background."""
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if not doc:
            return
        try:
            pages = extraction.extract_pdf(doc.stored_path)
            doc.page_count = len(pages)
            doc.ocr_pages = sum(p.ocr for p in pages)
            doc.ocr_used = doc.ocr_pages > 0
            doc.char_count = sum(len(p.text) for p in pages)

            session.exec(delete(Chunk).where(Chunk.document_id == doc_id))
            for page, text in extraction.chunk_pages(pages):
                session.add(Chunk(document_id=doc_id, course_id=doc.course_id, chapter_id=doc.chapter_id,
                                  page=page, text=text))

            if doc.kind == "booklet":
                store_booklet_exercises(session, doc, pages)

            if doc.char_count == 0:
                doc.status = "error"
                doc.error = (
                    "No text could be extracted, even with OCR." if extraction.ocr_available() else
                    "No text found. The PDF looks scanned and OCR is unavailable: install Tesseract "
                    "with the French and English language packs (see README)."
                )
            else:
                doc.status = "ready"
                doc.error = None
        except Exception as exc:  # keep the app usable and surface the error in the UI
            log.exception("Processing document %s failed", doc_id)
            doc.status = "error"
            doc.error = str(exc)[:500]
        session.add(doc)
        session.commit()


def store_booklet_exercises(session: Session, doc: Document, pages) -> int:
    session.exec(delete(BookletExercise).where(BookletExercise.document_id == doc.id))
    parsed = booklet_parser.parse_booklet(pages)
    chapter_cache: dict[str, int] = {}
    for i, ex in enumerate(parsed):
        chapter_id = doc.chapter_id
        if chapter_id is None and ex.chapter_title:
            chapter_id = _chapter_for_title(session, doc.course_id, ex.chapter_title, chapter_cache)
        session.add(BookletExercise(
            document_id=doc.id, course_id=doc.course_id, chapter_id=chapter_id, label=ex.label,
            position=i, raw_text=ex.raw_text, statement=ex.statement, given_data=ex.given_data,
            sub_questions=ex.sub_questions, correction=ex.correction,
            correction_source="booklet" if ex.correction else "none",
            page_start=ex.page_start, page_end=ex.page_end,
        ))
    return len(parsed)


def _chapter_for_title(session: Session, course_id: int, title: str, cache: dict[str, int]) -> int:
    """Map a heading like 'Chapitre 2 : Statique des fluides' to a chapter, creating it if needed."""
    if title in cache:
        return cache[title]
    m = booklet_parser.CHAPTER_RE.match(title)
    name = re.sub(r"\s+", " ", (m.group("title") if m and m.group("title").strip() else title)).strip()
    folded = name.lower()
    chapters = session.exec(select(Chapter).where(Chapter.course_id == course_id)).all()
    for ch in chapters:
        if ch.name.lower() == folded or (len(ch.name) > 4 and ch.name.lower() in folded):
            cache[title] = ch.id
            return ch.id
    ch = Chapter(course_id=course_id, name=name, position=len(chapters))
    session.add(ch)
    session.flush()
    cache[title] = ch.id
    return ch.id
