from __future__ import annotations

from typing import Any

VALID_SOURCE_TYPES = {
    "real_experience",
    "imagined_setting",
    "topic_requirement",
    "observation",
    "reading_material",
    "child_confirmed",
}
FACT_SOURCE_TYPES = {"reading_material", "observation", "child_confirmed"}


def _clean(value: Any) -> str:
    return "".join(str(value or "").split())


def normalize_source_refs(source_refs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for ref in source_refs or []:
        if not isinstance(ref, dict):
            raise ValueError("source_refs must contain objects")
        source_type = str(ref.get("source_type") or "").strip()
        if source_type == "ai_suggestion":
            raise ValueError("AI suggestion IDs alone are not valid sources")
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"unknown source_type: {source_type}")
        normalized.append({**ref, "source_type": source_type})
    return normalized


def _topic_requirement_explicitly_contains(text: str, ref: dict[str, Any]) -> bool:
    quote = _clean(ref.get("quote_or_summary"))
    claim = _clean(text)
    return bool(claim and quote and claim in quote)


def validate_expository_fact_sources(text: str, source_refs: list[dict[str, Any]]) -> None:
    refs = normalize_source_refs(source_refs)
    if not str(text or "").strip():
        return
    if any(ref["source_type"] in FACT_SOURCE_TYPES for ref in refs):
        return
    topic_refs = [ref for ref in refs if ref["source_type"] == "topic_requirement"]
    if topic_refs and any(_topic_requirement_explicitly_contains(text, ref) for ref in topic_refs):
        return
    if topic_refs:
        raise ValueError("topic_requirement does not explicitly contain factual claim")
    raise ValueError("expository factual content requires reading_material, observation, or child_confirmed source")
