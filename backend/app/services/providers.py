"""LLM providers ExamForge can use. Add one by appending to PROVIDERS; most new services only need a
`chat_completions` entry, since they speak the OpenAI Chat Completions format."""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PROVIDER = "anthropic"


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    api: str  # "anthropic" (native SDK) or "chat_completions" (OpenAI-compatible HTTP)
    default_model: str
    suggested_models: tuple[str, ...]
    key_env: str | None  # None = no key needed (local models)
    key_url: str = ""  # where to create a key
    base_url: str = ""  # chat_completions only
    base_url_env: str | None = None  # set when the user can change the URL (e.g. Ollama on another machine)
    json_mode: bool = True  # send response_format={"type": "json_object"}
    max_tokens_param: str = "max_tokens"
    max_output_tokens: int = 32000
    vision: bool = True  # accepts page images (used by "Re-transcribe")

    @property
    def name(self) -> str:
        """Short name for messages, e.g. "Claude" or "Ollama"."""
        return self.label.split(" (")[0]

    @property
    def model_env(self) -> str:
        return f"{self.id.upper()}_MODEL"

    @property
    def model(self) -> str:
        return os.getenv(self.model_env) or self.default_model

    @property
    def api_key(self) -> str:
        return os.getenv(self.key_env, "") if self.key_env else ""

    @property
    def configured(self) -> bool:
        return self.key_env is None or bool(self.api_key)

    @property
    def url(self) -> str:
        return ((os.getenv(self.base_url_env) if self.base_url_env else None) or self.base_url).rstrip("/")


PROVIDERS: dict[str, Provider] = {p.id: p for p in (
    Provider(
        id="anthropic", label="Claude (Anthropic)", api="anthropic",
        default_model="claude-opus-5-5",
        suggested_models=("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"),
        key_env="ANTHROPIC_API_KEY", key_url="https://console.anthropic.com/settings/keys",
        max_output_tokens=64000,
    ),
    Provider(
        id="openai", label="OpenAI (GPT)", api="chat_completions",
        default_model="gpt-6-astra", suggested_models=("gpt-6-astra", "gpt-6-luna"),
        key_env="OPENAI_API_KEY", key_url="https://platform.openai.com/api-keys",
        base_url="https://api.openai.com/v1", max_tokens_param="max_completion_tokens",
    ),
    Provider(
        id="google", label="Google AI (Gemini)", api="chat_completions",
        default_model="gemini-4-argon",
        suggested_models=("gemini-4-argon", "gemini-3.8-flash", "gemini-3.5-flash-lite"),
        key_env="GOOGLE_API_KEY", key_url="https://aistudio.google.com/apikey",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    Provider(
        id="deepseek", label="DeepSeek", api="chat_completions",
        default_model="deepseek-v4-pro", suggested_models=("deepseek-v4-pro", "deepseek-flash"),
        key_env="DEEPSEEK_API_KEY", key_url="https://platform.deepseek.com/api_keys",
        base_url="https://api.deepseek.com", max_output_tokens=8000, vision=False,
    ),
    Provider(
        id="xai", label="Grok (xAI)", api="chat_completions",
        default_model="grok-4.7", suggested_models=("grok-4.7",),
        key_env="XAI_API_KEY", key_url="https://console.x.ai",
        base_url="https://api.x.ai/v1",
    ),
    Provider(
        id="ollama", label="Ollama (local, Qwen)", api="chat_completions",
        default_model="qwen3:8b", suggested_models=("qwen3:8b", "qwen3:14b", "qwen3:30b", "qwen3:4b"),
        key_env=None, base_url="http://localhost:11434/v1", base_url_env="OLLAMA_BASE_URL",
        max_output_tokens=16000, vision=False,
    ),
)}


def active() -> Provider:
    return PROVIDERS.get(os.getenv("EXAMFORGE_PROVIDER", ""), PROVIDERS[DEFAULT_PROVIDER])
