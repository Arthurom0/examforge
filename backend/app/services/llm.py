"""Claude API calls. All outputs use structured outputs and are validated before they are stored."""
from __future__ import annotations

import base64
import logging
import os
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from ..config import settings
from ..schemas import GeneratedProblem, GeneratedSolution, ProblemBatch
from .prompts import SYSTEM

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


_client: anthropic.Anthropic | None = None
_client_key: str | None = None


def client() -> anthropic.Anthropic:
    global _client, _client_key
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("No Anthropic API key configured. Add it in Settings.")
    if _client is None or key != _client_key:  # the key can change from the Settings page
        _client, _client_key = anthropic.Anthropic(api_key=key), key
    return _client


def call_structured(content: str | list, schema: type[T], *, system: str = SYSTEM,
                    max_tokens: int = 64000) -> T:
    """One streamed request whose final message is parsed into `schema`."""
    try:
        with client().messages.stream(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
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
        raise LLMError("Claude returned problems that failed validation twice. Try again or change the options.")
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
        raise LLMError("Claude returned an empty solution.")
    return sol


def image_block(png: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.b64encode(png).decode()}}
