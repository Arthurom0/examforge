"""Every provider adapter, with the HTTP/SDK layer mocked (no real keys in tests)."""
import json
import os
from pathlib import Path

import httpx
import pytest

from app.schemas import GeneratedSolution, ProblemBatch
from app.services import llm, providers

SOLUTION = {"answer": "v = 5,6 m/s", "topic_tags": ["venturi"], "self_check": "unités ok", "confidence": "high",
            "assumptions": "", "solution_steps": [{"title": "a)", "content": "$v = \\sqrt{2 g h}$"}]}

PROBLEM = {"title": "Venturi", "type": "numerical", "difficulty": "exam", "statement": "Calculer $v_2$.",
           "given_data": [{"symbol": "D_1", "value": "0.1", "unit": "m", "description": "diamètre"}],
           "choices": [], "answer": "v_2 = 5,6 m/s",
           "solution_steps": [{"title": "Continuité", "content": "..."}, {"title": "Bernoulli", "content": "..."}],
           "topic_tags": ["Venturi"], "self_check": "Recalculé, unités cohérentes."}


@pytest.fixture(autouse=True)
def clean_env():
    """Settings writes to os.environ and the .env file; put both back after each test."""
    env_file = Path(os.environ["EXAMFORGE_ENV_FILE"])
    saved_file = env_file.read_text() if env_file.exists() else None
    saved_env = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved_env)
    if saved_file is None:
        env_file.unlink(missing_ok=True)
    else:
        env_file.write_text(saved_file)


class FakeHTTP:
    """Stands in for httpx.post: records requests, replays queued responses."""

    def __init__(self, monkeypatch, *responses):
        self.requests = []
        self.responses = list(responses)
        monkeypatch.setattr(llm.httpx, "post", self)

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.requests.append({"url": url, "json": json, "headers": headers or {}})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        status, body = r
        return httpx.Response(status, json=body, request=httpx.Request("POST", url))


def reply(content, finish="stop"):
    return 200, {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}


def use(monkeypatch, provider_id, key="test-key-123456789"):
    monkeypatch.setenv("EXAMFORGE_PROVIDER", provider_id)
    p = providers.PROVIDERS[provider_id]
    if p.key_env:
        monkeypatch.setenv(p.key_env, key)
    return p


@pytest.mark.parametrize("pid,url,model", [
    ("openai", "https://api.openai.com/v1/chat/completions", "gpt-6-astra"),
    ("google", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-4-argon"),
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-v4-pro"),
    ("xai", "https://api.x.ai/v1/chat/completions", "grok-4.7"),
    ("ollama", "http://localhost:11434/v1/chat/completions", "qwen3:8b"),
])
def test_chat_providers_request_and_parse(monkeypatch, pid, url, model):
    p = use(monkeypatch, pid)
    http = FakeHTTP(monkeypatch, reply(json.dumps(SOLUTION)))
    sol = llm.call_structured("Résoudre l'exercice", GeneratedSolution, max_tokens=64000)
    assert sol.answer == "v = 5,6 m/s"
    req = http.requests[0]
    assert req["url"] == url
    assert req["json"]["model"] == model
    assert req["json"]["response_format"] == {"type": "json_object"}
    assert req["json"][p.max_tokens_param] == p.max_output_tokens  # capped per provider
    system = req["json"]["messages"][0]["content"]
    assert "SI" in system and "JSON Schema" in system and '"solution_steps"' in system  # same prompt + schema
    if p.key_env:
        assert req["headers"]["Authorization"] == "Bearer test-key-123456789"
    else:
        assert "Authorization" not in req["headers"]


def test_openai_uses_max_completion_tokens(monkeypatch):
    use(monkeypatch, "openai")
    http = FakeHTTP(monkeypatch, reply(json.dumps(SOLUTION)))
    llm.call_structured("x", GeneratedSolution, max_tokens=16000)
    assert http.requests[0]["json"]["max_completion_tokens"] == 16000
    assert "max_tokens" not in http.requests[0]["json"]


def test_model_and_ollama_url_overrides(monkeypatch):
    use(monkeypatch, "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:30b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.20:11434/v1/")
    http = FakeHTTP(monkeypatch, reply(json.dumps(SOLUTION)))
    llm.call_structured("x", GeneratedSolution)
    assert http.requests[0]["url"] == "http://192.168.1.20:11434/v1/chat/completions"
    assert http.requests[0]["json"]["model"] == "qwen3:30b"


def test_qwen_thinking_and_code_fences_are_stripped(monkeypatch):
    use(monkeypatch, "ollama")
    content = "<think>Je vérifie les unités…</think>\nVoici:\n```json\n" + json.dumps(SOLUTION) + "\n```"
    FakeHTTP(monkeypatch, reply(content))
    assert llm.call_structured("x", GeneratedSolution).confidence == "high"


def test_invalid_json_gets_one_repair_round(monkeypatch):
    use(monkeypatch, "deepseek")
    broken = dict(SOLUTION, confidence="very")  # not an allowed value
    http = FakeHTTP(monkeypatch, reply(json.dumps(broken)), reply(json.dumps(SOLUTION)))
    assert llm.call_structured("x", GeneratedSolution).confidence == "high"
    repair = http.requests[1]["json"]["messages"]
    assert repair[-2]["role"] == "assistant" and "confidence" in repair[-1]["content"]

    FakeHTTP(monkeypatch, reply("not json"), reply("still not json"))
    with pytest.raises(llm.LLMError, match="could not be parsed"):
        llm.call_structured("x", GeneratedSolution)


def test_json_mode_rejected_falls_back_to_instructions(monkeypatch):
    use(monkeypatch, "xai")
    http = FakeHTTP(monkeypatch, (400, {"error": {"message": "response_format is not supported"}}),
                    reply(json.dumps(SOLUTION)))
    llm.call_structured("x", GeneratedSolution)
    assert "response_format" not in http.requests[1]["json"]


def test_generation_validation_and_self_check_apply_to_other_providers(monkeypatch):
    use(monkeypatch, "google")
    no_check = dict(PROBLEM, self_check="")
    http = FakeHTTP(monkeypatch, reply(json.dumps({"problems": [no_check]})),
                    reply(json.dumps({"problems": [PROBLEM]})))
    problems = llm.generate_validated("Génère 1 problème", 1, ["numerical"])
    assert len(problems) == 1 and problems[0].topic_tags == ["venturi"]
    retry_prompt = http.requests[1]["json"]["messages"][1]["content"]
    assert "missing self_check" in retry_prompt


@pytest.mark.parametrize("status,match", [(401, "key was rejected"), (429, "Rate limited"), (404, "doesn't know")])
def test_http_errors_are_readable(monkeypatch, status, match):
    use(monkeypatch, "openai")
    FakeHTTP(monkeypatch, (status, {"error": {"message": "nope"}}))
    with pytest.raises(llm.LLMError, match=match):
        llm.call_structured("x", GeneratedSolution)


def test_ollama_not_running_or_model_missing(monkeypatch):
    use(monkeypatch, "ollama")
    FakeHTTP(monkeypatch, httpx.ConnectError("refused"))
    with pytest.raises(llm.LLMError, match="Could not reach Ollama.*ollama pull qwen3:8b"):
        llm.call_structured("x", GeneratedSolution)
    FakeHTTP(monkeypatch, (404, {"error": {"message": "model not found"}}))
    with pytest.raises(llm.LLMError, match="ollama pull"):
        llm.call_structured("x", GeneratedSolution)


def test_missing_key_is_reported_per_provider(monkeypatch):
    monkeypatch.setenv("EXAMFORGE_PROVIDER", "xai")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(llm.LLMError, match="No Grok API key"):
        llm.call_structured("x", GeneratedSolution)


def test_page_images(monkeypatch):
    use(monkeypatch, "openai")
    http = FakeHTTP(monkeypatch, reply(json.dumps(SOLUTION)))
    llm.call_structured([llm.image_block(b"\x89PNG"), {"type": "text", "text": "Transcris"}], GeneratedSolution)
    parts = http.requests[0]["json"]["messages"][1]["content"]
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert parts[1] == {"type": "text", "text": "Transcris"}

    use(monkeypatch, "deepseek")
    with pytest.raises(llm.LLMError, match="cannot read page images"):
        llm.call_structured([llm.image_block(b"\x89PNG")], GeneratedSolution)


def test_anthropic_stays_the_default(monkeypatch):
    monkeypatch.delenv("EXAMFORGE_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123456789")
    seen = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return type("M", (), {"stop_reason": "end_turn", "parsed_output": ProblemBatch(problems=[])})()

    class Client:
        class messages:  # noqa: N801
            @staticmethod
            def stream(**kwargs):
                seen.update(kwargs)
                return Stream()

    monkeypatch.setattr(llm, "client", lambda key: Client)
    llm.call_structured("x", ProblemBatch)
    assert seen["model"] == "claude-opus-5-5" and seen["output_format"] is ProblemBatch
    assert seen["output_config"] == {"effort": "high"}


def test_settings_per_provider_keys(client):
    r = client.put("/api/settings", json={"provider": "openai", "api_key": "sk-proj-abcdef123456"}).json()
    assert r["provider"] == "openai" and r["api_key_configured"] and r["api_key_hint"] == "…3456"
    assert r["model"] == "gpt-6-astra"
    assert "sk-proj-abcdef" not in str(r)
    env_text = Path(os.environ["EXAMFORGE_ENV_FILE"]).read_text()
    assert "OPENAI_API_KEY=sk-proj-abcdef123456" in env_text and "EXAMFORGE_PROVIDER=openai" in env_text

    r = client.put("/api/settings", json={"provider": "openai", "model": "gpt-6-luna"}).json()
    assert r["model"] == "gpt-6-luna"
    r = client.put("/api/settings", json={"provider": "openai", "model": ""}).json()
    assert r["model"] == "gpt-6-astra"

    r = client.put("/api/settings", json={"provider": "ollama", "base_url": "http://mac-mini:11434/v1"}).json()
    ollama = next(p for p in r["providers"] if p["id"] == "ollama")
    assert r["api_key_configured"] and not ollama["needs_key"] and ollama["base_url"] == "http://mac-mini:11434/v1"
    assert client.get("/api/health").json()["provider"] == "ollama"
    openai = next(p for p in r["providers"] if p["id"] == "openai")
    assert openai["key_configured"]  # other providers keep their keys

    assert client.put("/api/settings", json={"provider": "nope"}).status_code == 422
