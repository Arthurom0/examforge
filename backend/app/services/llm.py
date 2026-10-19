"""LLM calls for every provider. All outputs are parsed into Pydantic schemas and validated before they are stored."""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import TypeVar

import anthropic
import httpx
from pydantic import BaseModel, ValidationError

from ..config import settings
from ..schemas import GeneratedProblem, GeneratedSolution, ProblemBatch
from . import providers
from .prompts import SYSTEM
from .providers import Provider

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def call_structured(content: str | list, schema: type[T], *, system: str = SYSTEM,
                    max_tokens: int = 64000) -> T:
    """One request to the provider chosen in Settings, parsed into `schema`.

    `content` is a string or a list of Anthropic-style blocks (text and image_block()); adapters convert it."""
    provider = providers.active()
    if not provider.configured:
        raise LLMError(f"No {provider.name} API key configured. Add it in Settings.")
    if provider.api == "anthropic":
        return _anthropic_call(provider, content, schema, system, max_tokens)
    return _chat_completions_call(provider, content, schema, system, max_tokens)


# ---------- Anthropic (native structured outputs) ----------

_client: anthropic.Anthropic | None = None
_client_key: str | None = None


def client(key: str) -> anthropic.Anthropic:
    global _client, _client_key
    if _client is None or key != _client_key:  # the key can change from the Settings page
        _client, _client_key = anthropic.Anthropic(api_key=key), key
    return _client


def _anthropic_call(provider: Provider, content, schema: type[T], system: str, max_tokens: int) -> T:
    try:
        with client(provider.api_key).messages.stream(
            model=provider.model,
            max_tokens=min(max_tokens, provider.max_output_tokens),
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": settings.anthropic_effort},
            messages=[{"role": "user", "content": content}],
            output_format=schema,
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as exc:
        raise LLMError("The Anthropic API key was rejected. Check it in Settings.") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError("Rate limited by the Anthropic API. Wait a minute and try again.") from exc
    except anthropic.BadRequestError as exc:
        raise LLMError(f"The API rejected the request: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError("Could not reach the Anthropic API. Check your internet connection.") from exc

    if message.stop_reason == "refusal":
        raise LLMError("Claude declined this request. Try rephrasing the focus or a different chapter.")
    if message.stop_reason == "max_tokens":
        raise LLMError("The response was cut off. Ask for fewer problems at a time.")
    parsed = message.parsed_output
    if parsed is None:
        raise LLMError("Claude's response could not be parsed as the expected JSON.")
    return parsed


# ---------- OpenAI-compatible Chat Completions (OpenAI, Gemini, DeepSeek, Grok, Ollama) ----------

JSON_INSTRUCTIONS = """

Reply with exactly one JSON object and nothing else: no prose, no Markdown code fences.
It must validate against this JSON Schema (every field is required; use "" or [] when there is nothing to put):
{schema}"""


def _chat_messages(provider: Provider, content, system: str, schema: type[BaseModel]) -> list[dict]:
    if isinstance(content, str):
        user = content
    else:
        user = []
        for block in content:
            if block.get("type") == "image":
                if not provider.vision:
                    raise LLMError(f"{provider.name} ({provider.model}) cannot read page images. "
                                   "Switch to a provider with vision in Settings for this action.")
                src = block["source"]
                user.append({"type": "image_url",
                             "image_url": {"url": f"data:{src['media_type']};base64,{src['data']}"}})
            else:
                user.append({"type": "text", "text": block.get("text", "")})
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    return [{"role": "system", "content": system + JSON_INSTRUCTIONS.format(schema=schema_json)},
            {"role": "user", "content": user}]


def _post(provider: Provider, payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {provider.api_key}"} if provider.api_key else {}
    url = f"{provider.url}/chat/completions"
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=httpx.Timeout(900, connect=10))
    except httpx.ConnectError as exc:
        if provider.id == "ollama":
            raise LLMError(f"Could not reach Ollama at {provider.url}. Start the Ollama app, then run "
                           f"`ollama pull {provider.model}` once.") from exc
        raise LLMError(f"Could not reach the {provider.name} API. Check your internet connection.") from exc
    except httpx.TimeoutException as exc:
        raise LLMError(f"{provider.name} took too long to answer. Ask for fewer problems at a time.") from exc
    if r.status_code >= 400:
        detail = _error_detail(r)
        if r.status_code in (401, 403):
            raise LLMError(f"The {provider.name} API key was rejected. Check it in Settings. ({detail})")
        if r.status_code == 429:
            raise LLMError(f"Rate limited by {provider.name} (or out of credit). Wait and try again. ({detail})")
        if r.status_code == 404 and provider.id == "ollama":
            raise LLMError(f"Ollama doesn't have {provider.model}. Run `ollama pull {provider.model}` first.")
        if r.status_code == 404:
            raise LLMError(f"{provider.name} doesn't know the model '{provider.model}'. Pick another in Settings.")
        raise _StatusError(r.status_code, f"{provider.name} API error ({r.status_code}): {detail}")
    return r.json()


class _StatusError(LLMError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _error_detail(r: httpx.Response) -> str:
    try:
        body = r.json()
        if isinstance(body, list) and body:  # Gemini sometimes wraps errors in a list
            body = body[0]
        err = body.get("error", body)
        return str(err.get("message", err) if isinstance(err, dict) else err)[:300]
    except ValueError:
        return r.text[:300]


def _complete(provider: Provider, messages: list[dict], max_tokens: int) -> str:
    payload = {"model": provider.model, "messages": messages,
               provider.max_tokens_param: min(max_tokens, provider.max_output_tokens)}
    if provider.json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        data = _post(provider, payload)
    except _StatusError as exc:
        if exc.status != 400 or "response_format" not in payload:
            raise
        payload.pop("response_format")  # some models reject JSON mode; the instructions still ask for JSON
        data = _post(provider, payload)
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        raise LLMError("The response was cut off. Ask for fewer problems at a time.")
    if choice.get("finish_reason") == "content_filter":
        raise LLMError(f"{provider.name} declined this request. Try rephrasing the focus or a different chapter.")
    text = (choice.get("message") or {}).get("content") or ""
    if isinstance(text, list):  # content parts
        text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
    return text


def extract_json(text: str) -> str:
    """The JSON object inside a reply that may carry <think> blocks or code fences."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start != -1 and end > start else text


def _chat_completions_call(provider: Provider, content, schema: type[T], system: str, max_tokens: int) -> T:
    messages = _chat_messages(provider, content, system, schema)
    text = _complete(provider, messages, max_tokens)
    try:
        return schema.model_validate_json(extract_json(text))
    except ValidationError as exc:
        # One repair round with the exact errors; smaller models often get the structure right on the second try.
        log.info("Repairing %s JSON: %s", provider.id, exc.error_count())
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "That reply is not valid against the schema:\n"
                      f"{_short_errors(exc)}\nSend the corrected JSON object only."}]
        text = _complete(provider, messages, max_tokens)
        try:
            return schema.model_validate_json(extract_json(text))
        except ValidationError as exc2:
            raise LLMError(f"{provider.name}'s response could not be parsed as the expected JSON. "
                           "Try again, or use a larger model.") from exc2


def _short_errors(exc: ValidationError) -> str:
    return "\n".join(f"- {'.'.join(map(str, e['loc'])) or 'root'}: {e['msg']}" for e in exc.errors()[:15])


# ---------- validation shared by every provider ----------

def validate_problem(p: GeneratedProblem, expected_types: list[str] | None = None) -> list[str]:
    """Checks the schema cannot express. Returns a list of problems (empty if valid)."""
    errors = []
    if not p.statement.strip():
        errors.append("empty statement")
    if len(p.solution_steps) < 2:
        errors.append("solution needs at least 2 steps")
    if not p.answer.strip():
        errors.append("empty answer")
    if not p.topic_tags:
        errors.append("missing topic_tags")
    if not p.self_check.strip():
        errors.append("missing self_check")
    if expected_types and p.type not in expected_types:
        errors.append(f"type '{p.type}' was not requested")
    if p.type == "mcq":
        labels = [c.label.strip().upper() for c in p.choices]
        if len(p.choices) < 3:
            errors.append("mcq needs at least 3 choices")
        elif not any(p.answer.strip().upper().startswith(lbl) or f"({lbl})" in p.answer.upper() for lbl in labels):
            errors.append("mcq answer does not name one of the choice labels")
    elif p.type == "numerical":
        if not p.given_data:
            errors.append("numerical problem has no given_data")
        if not any(ch.isdigit() for ch in p.answer):
            errors.append("numerical answer contains no number")
        missing_units = [g.symbol for g in p.given_data if not g.unit.strip() and not _dimensionless(g)]
        if len(missing_units) > max(1, len(p.given_data) // 2):
            errors.append(f"given data without units: {', '.join(missing_units)}")
    return errors


def _dimensionless(g) -> bool:
    text = f"{g.description} {g.symbol}".lower()
    return any(w in text for w in ("sans dimension", "dimensionless", "adimension", "nombre", "number",
                                   "coefficient", "ratio", "rapport", "gamma", "efficiency", "rendement"))


def generate_validated(prompt: str, count: int, types: list[str] | None) -> list[GeneratedProblem]:
    """Generate, validate, and retry once with the validation errors if anything is off."""
    batch = call_structured(prompt, ProblemBatch)
    problems, report = _check(batch.problems, types)
    if report or len(problems) < count:
        log.info("Retrying generation: %s", report)
        feedback = (f"{prompt}\n\nA previous attempt had these issues; avoid them:\n" + "\n".join(report)
                    if report else prompt)
        retry = call_structured(feedback, ProblemBatch)
        retry_ok, _ = _check(retry.problems, types)
        if len(retry_ok) > len(problems):
            problems = retry_ok
    if not problems:
        raise LLMError(f"{providers.active().name} returned problems that failed validation twice. "
                       "Try again or change the options.")
    return problems[:count]


def _check(problems: list[GeneratedProblem], types: list[str] | None) -> tuple[list[GeneratedProblem], list[str]]:
    ok, report = [], []
    for i, p in enumerate(problems, start=1):
        errs = validate_problem(p, types)
        if errs:
            report.append(f"- problem {i}: {'; '.join(errs)}")
        else:
            p.topic_tags = [t.strip().lower() for t in p.topic_tags if t.strip()][:3]
            ok.append(p)
    return ok, report


def solve(prompt: str) -> GeneratedSolution:
    sol = call_structured(prompt, GeneratedSolution)
    if not sol.solution_steps:
        raise LLMError(f"{providers.active().name} returned an empty solution.")
    return sol


def image_block(png: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.b64encode(png).decode()}}
