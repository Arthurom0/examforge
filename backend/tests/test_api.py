"""API flow with Claude mocked out: upload -> booklet split -> generate -> attempts -> stats."""
import time

import pytest

from app.schemas import (GeneratedProblem, GeneratedSolution, GivenItem, ProblemBatch, SolutionStep)
from app.services import llm

from .fixtures import make_booklet, make_lecture


def fake_problem(i: int, ptype: str = "numerical", tags=("bernoulli",)) -> GeneratedProblem:
    return GeneratedProblem(
        title=f"Probleme {i}", type=ptype, difficulty="medium",
        statement="Un Venturi... calculer $v_2$.",
        given_data=[GivenItem(symbol="S_1", value="20", unit="cm^2", description="section d'entree"),
                    GivenItem(symbol="\\Delta p", value="15", unit="kPa", description="difference de pression")],
        choices=[], answer="v_2 = 5{,}6 m/s",
        solution_steps=[SolutionStep(title="Conservation du debit", content="$S_1 v_1 = S_2 v_2$"),
                        SolutionStep(title="Bernoulli", content="$p_1 + ...$")],
        topic_tags=list(tags), self_check="Recalcule, unites ok.",
    )


@pytest.fixture
def mock_claude(monkeypatch):
    calls = []

    def fake_call(content, schema, **kwargs):
        calls.append(content)
        if schema is ProblemBatch:
            return ProblemBatch(problems=[fake_problem(i) for i in range(3)])
        if schema is GeneratedSolution:
            return GeneratedSolution(answer="v = 5,6 m/s", topic_tags=["venturi"], self_check="ok",
                                     confidence="medium", assumptions="",
                                     solution_steps=[SolutionStep(title="a)", content="...")])
        raise AssertionError(f"unexpected schema {schema}")

    monkeypatch.setattr(llm, "call_structured", fake_call)
    return calls


def wait_ready(client, doc_id):
    for _ in range(50):
        doc = client.get(f"/api/documents/{doc_id}").json()
        if doc["status"] != "pending":
            return doc
        time.sleep(0.1)
    raise TimeoutError


def test_full_flow(client, tmp_path, mock_claude):
    course = client.post("/api/courses", json={"name": "Mécanique des fluides"}).json()
    ch = client.post(f"/api/courses/{course['id']}/chapters", json={"name": "Dynamique des fluides parfaits"}).json()

    with open(make_lecture(tmp_path / "cours.pdf"), "rb") as f:
        lec = client.post("/api/documents", data={"course_id": course["id"], "kind": "lecture", "chapter_id": ch["id"]},
                          files={"file": ("cours.pdf", f, "application/pdf")}).json()
    assert wait_ready(client, lec["id"])["status"] == "ready"

    with open(make_booklet(tmp_path / "td.pdf"), "rb") as f:
        bk = client.post("/api/documents", data={"course_id": course["id"], "kind": "booklet"},
                         files={"file": ("td.pdf", f, "application/pdf")}).json()
    assert wait_ready(client, bk["id"])["status"] == "ready"

    exs = client.get("/api/exercises", params={"document_id": bk["id"]}).json()
    assert len(exs) == 3
    # chapters detected from headings: "Chapitre 2 : Dynamique..." maps onto the existing chapter
    assert exs[2]["chapter_id"] == ch["id"]
    names = {c["name"] for c in next(c for c in client.get("/api/courses").json() if c["id"] == course["id"])["chapters"]}
    assert names == {"Dynamique des fluides parfaits", "Statique des fluides"}
    assert exs[0]["correction_source"] == "booklet" and exs[2]["correction_source"] == "none"

    # Fix the split: merge 1+2, then split again at the second header
    assert client.post(f"/api/exercises/{exs[0]['id']}/merge-next").status_code == 200
    merged = client.get(f"/api/exercises/{exs[0]['id']}").json()
    offset = merged["raw_text"].index("Exercice 2")
    r = client.post(f"/api/exercises/{exs[0]['id']}/split", json={"offset": offset})
    assert r.status_code == 200
    exs = client.get("/api/exercises", params={"document_id": bk["id"]}).json()
    assert [e["label"][:10] for e in exs] == ["Exercice 1", "Exercice 2", "Exercice 3"]

    # Solve mode on the exercise without correction -> labelled AI
    solved = client.post(f"/api/exercises/{exs[2]['id']}/solve").json()
    assert solved["correction_source"] == "ai" and solved["topic_tags"] == ["venturi"]
    # but refuses when the booklet already has a correction
    assert client.post(f"/api/exercises/{exs[0]['id']}/solve").status_code == 400

    # Generation: retrieved chunks and booklet references reach the prompt
    gen = client.post("/api/generate", json={"course_id": course["id"], "chapter_id": ch["id"], "count": 2,
                                             "types": ["numerical"], "difficulty": "exam", "language": "fr"})
    assert gen.status_code == 200, gen.text
    ps = gen.json()
    assert len(ps["problems"]) == 2
    prompt = mock_claude[-1]
    assert "Bernoulli" in prompt and "<booklet_exercise>" in prompt and "Venturi" in prompt

    # Variants
    var = client.post(f"/api/exercises/{exs[2]['id']}/variants", json={"count": 2}).json()
    assert var["mode"] == "variant" and var["source_exercise_id"] == exs[2]["id"]

    # Attempts, tracked separately per origin
    p1, p2 = ps["problems"]
    client.post("/api/attempts", json={"problem_id": p1["id"], "result": "wrong"})
    client.post("/api/attempts", json={"problem_id": p2["id"], "result": "partial"})
    client.post("/api/attempts", json={"exercise_id": exs[2]["id"], "result": "correct"})
    ov = client.get("/api/stats/overview").json()
    c = next(x for x in ov if x["course_id"] == course["id"])
    assert c["attempts"] == 3
    assert c["generated"]["success_rate"] == 0.25 and c["booklet"]["success_rate"] == 1.0

    weak = client.get("/api/stats/weak-topics", params={"course_id": course["id"]}).json()
    assert weak[0]["topic"] == "bernoulli"

    tl = client.get("/api/stats/timeline", params={"course_id": course["id"]}).json()
    assert tl["periods"] and any(s["key"] == "all" for s in tl["series"])

    # Weak-spot generation feeds the weak topic into the prompt
    gen = client.post("/api/generate", json={"course_id": course["id"], "count": 1, "weak_spot": True})
    assert gen.json()["mode"] == "weak_spot"
    assert "bernoulli" in mock_claude[-1]


def test_validation_rejects_bad_mcq():
    p = fake_problem(1, "mcq")
    assert any("choices" in e for e in llm.validate_problem(p))
    assert llm.validate_problem(fake_problem(2)) == []
