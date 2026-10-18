import pytest

from app.services import booklet_parser, extraction, retrieval

from .fixtures import make_booklet, make_lecture, make_scanned


def test_text_extraction_and_chunks(tmp_path):
    pages = extraction.extract_pdf(str(make_lecture(tmp_path / "cours.pdf")))
    assert len(pages) == 2 and not any(p.ocr for p in pages)
    assert "Bernoulli" in pages[0].text
    chunks = extraction.chunk_pages(pages, size=200, overlap=40)
    assert len(chunks) > 2 and {c[0] for c in chunks} == {1, 2}


def test_booklet_split(tmp_path):
    pages = extraction.extract_pdf(str(make_booklet(tmp_path / "td.pdf")))
    exs = booklet_parser.parse_booklet(pages)
    assert [e.number for e in exs] == [1, 2, 3]
    ex1, ex2, ex3 = exs
    # inline correction
    assert ex1.correction and "16 010" in ex1.correction
    assert [q["label"] for q in ex1.sub_questions] == ["a", "b"]
    assert "13600" in ex1.given_data
    # correction from the "Corrigés" section at the end
    assert ex2.correction and "98,1" in ex2.correction
    assert [q["label"] for q in ex2.sub_questions] == ["1", "2"]
    assert "Chapitre" not in ex2.sub_questions[-1]["text"]
    assert ex3.correction is None
    assert ex3.page_start == 2
    assert ex1.chapter_title.startswith("Chapitre 1") and ex3.chapter_title.startswith("Chapitre 2")


def test_reparse_block():
    fields = booklet_parser.reparse_block("Exercice 7 : Pitot\nOn mesure p0 - p = 500 Pa.\na) Calculer v.\nb) Conclure.")
    assert fields["label"].startswith("Exercice 7")
    assert len(fields["sub_questions"]) == 2


@pytest.mark.skipif(not extraction.ocr_available(), reason="tesseract not installed")
def test_ocr_fallback(tmp_path):
    pages = extraction.extract_pdf(str(make_scanned(tmp_path / "scan.pdf")))
    assert pages[0].ocr
    assert "Exercice" in pages[0].text and "mercure" in pages[0].text
    exs = booklet_parser.parse_booklet(pages)
    assert len(exs) >= 2


def test_bm25_prefers_relevant_text():
    docs = ["La perte de charge reguliere depend du nombre de Reynolds.",
            "Le theoreme de Bernoulli relie pression et vitesse.",
            "Cycle de Brayton et rendement thermique."]
    scores = retrieval.bm25_rank("pertes de charge Reynolds", docs)
    assert scores.index(max(scores)) == 0
    assert retrieval.fold("Écoulement") == "ecoulement"
