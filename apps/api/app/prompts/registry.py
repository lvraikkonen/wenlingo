from collections.abc import Callable
from dataclasses import dataclass


PayloadBuilder = Callable[[], dict]


@dataclass(frozen=True)
class PromptSpec:
    prompt_key: str
    version: str
    system_prompt_key: str
    system_prompt: str
    response_contract: str
    build_payload: PayloadBuilder | None = None


_PROMPTS: dict[str, PromptSpec] = {}


def register_prompt(prompt: PromptSpec) -> PromptSpec:
    if prompt.prompt_key in _PROMPTS:
        raise ValueError(f"duplicate prompt key: {prompt.prompt_key}")
    _PROMPTS[prompt.prompt_key] = prompt
    return prompt


def ensure_prompt_registry_loaded() -> None:
    import app.prompts  # noqa: F401


def get_prompt(prompt_key: str) -> PromptSpec:
    ensure_prompt_registry_loaded()
    return _PROMPTS[prompt_key]


def registered_prompts() -> dict[str, PromptSpec]:
    ensure_prompt_registry_loaded()
    return dict(_PROMPTS)
