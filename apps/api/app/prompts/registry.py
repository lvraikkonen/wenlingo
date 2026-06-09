from collections.abc import Callable
from dataclasses import dataclass
import importlib


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
_PROMPT_MODULES = (
    "app.prompts.essay_feedback",
    "app.prompts.revision_feedback",
    "app.prompts.sentence_challenge",
    "app.prompts.sentence_feedback",
)
_loaded = False


def register_prompt(prompt: PromptSpec) -> PromptSpec:
    if prompt.prompt_key in _PROMPTS:
        raise ValueError(f"duplicate prompt key: {prompt.prompt_key}")
    _PROMPTS[prompt.prompt_key] = prompt
    return prompt


def ensure_prompt_registry_loaded() -> None:
    global _loaded
    if _loaded:
        return
    for module_name in _PROMPT_MODULES:
        importlib.import_module(module_name)
    _loaded = True


def get_prompt(prompt_key: str) -> PromptSpec:
    ensure_prompt_registry_loaded()
    return _PROMPTS[prompt_key]


def registered_prompts() -> dict[str, PromptSpec]:
    ensure_prompt_registry_loaded()
    return dict(_PROMPTS)
