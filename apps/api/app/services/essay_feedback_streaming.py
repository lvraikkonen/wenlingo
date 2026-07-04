from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
import unicodedata

from pydantic import ValidationError

from app.services.llm_contracts import EssayFeedback


SECTION_ORDER = [
    "strengths",
    "improvements",
    "problem_monsters",
    "sentence_notes",
    "revision_tasks",
]
SECTION_PATTERN = re.compile(
    r"<(?P<name>strengths|improvements|problem_monsters|sentence_notes|revision_tasks)>"
    r"(?P<body>.*?)"
    r"</(?P=name)>",
    re.DOTALL,
)
OPENING_TAG_PATTERN = re.compile(
    r"^<(?P<name>strengths|improvements|problem_monsters|sentence_notes|revision_tasks)>"
)
SECTION_ITEM_LIMITS: dict[str, tuple[int, int]] = {
    "strengths": (2, 2),
    "improvements": (1, 3),
    "problem_monsters": (1, 3),
    "sentence_notes": (1, 3),
    "revision_tasks": (1, 1),
}
PREVIEW_SECTIONS = {"strengths", "improvements", "sentence_notes", "revision_tasks"}
ANTI_GHOSTWRITING_MARKERS = (
    "范文",
    "可以这样写：",
    "可以这样写:",
    "作文如下",
    "完整作文",
)


@dataclass(frozen=True)
class FeedbackSectionPreview:
    section: str
    items: list[str]


class StreamSectionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class EssayFeedbackSectionParser:
    def __init__(self, *, max_buffer_bytes: int = 12000, max_item_chars: int = 160):
        self.buffer = ""
        self.next_index = 0
        self.seen: set[str] = set()
        self.sections: dict[str, list[str]] = {}
        self.max_buffer_bytes = max_buffer_bytes
        self.max_item_chars = max_item_chars

    def feed(self, text_delta: str) -> list[FeedbackSectionPreview]:
        self.buffer += text_delta
        if len(self.buffer.encode("utf-8")) > self.max_buffer_bytes:
            raise StreamSectionError("STREAM_SECTION_TOO_LARGE", "section buffer exceeded limit")
        if "```" in self.buffer:
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "markdown code fence")

        emitted: list[FeedbackSectionPreview] = []
        while True:
            stripped = self.buffer.lstrip()
            if not stripped:
                self.buffer = ""
                return emitted
            if self.next_index >= len(SECTION_ORDER):
                if stripped:
                    raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "content after final section")
                return emitted

            opening_match = OPENING_TAG_PATTERN.match(stripped)
            if opening_match is not None:
                opened_name = opening_match.group("name")
                if opened_name in self.seen:
                    raise StreamSectionError("STREAM_SECTION_DUPLICATE", opened_name)
                expected = SECTION_ORDER[self.next_index]
                if opened_name != expected:
                    raise StreamSectionError("STREAM_SECTION_OUT_OF_ORDER", opened_name)
            else:
                if "<" in stripped or "\n" in stripped:
                    raise StreamSectionError("STREAM_SECTION_OUT_OF_ORDER", stripped[:40])
                return emitted

            match = SECTION_PATTERN.match(stripped)
            if match is None:
                return emitted

            name = match.group("name")
            body = match.group("body")
            if any(f"<{section}>" in body or f"</{section}>" in body for section in SECTION_ORDER):
                raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "nested section")

            items = _parse_section_items(name, body, self.max_item_chars)
            self.seen.add(name)
            self.sections[name] = items
            self.next_index += 1
            if name in PREVIEW_SECTIONS:
                emitted.append(FeedbackSectionPreview(section=name, items=items))
            self.buffer = stripped[match.end():]

    def build_feedback(self) -> EssayFeedback:
        return build_validated_feedback_from_sections(self.sections)


def _parse_section_items(section: str, body: str, max_item_chars: int) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("- "):
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
        item = stripped[2:].strip()
        if not item:
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
        items.append(item)

    min_items, max_items = SECTION_ITEM_LIMITS[section]
    if len(items) < min_items or len(items) > max_items:
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
    if any(_display_length(item) > max_item_chars for item in items):
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", section)
    if any(_looks_copy_ready(item) for item in items):
        raise StreamSectionError("STREAM_ANTI_GHOSTWRITING_BLOCKED", section)

    if section == "revision_tasks":
        for item in items:
            parts = item.split(" | ", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise StreamSectionError(
                    "STREAM_FINAL_SCHEMA_INVALID",
                    f"revision_task must be 'instruction | target', got: {item[:60]}",
                )
    return items


def _display_length(text: str) -> int:
    total = 0
    for char in text:
        total += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return total


def _looks_copy_ready(item: str) -> bool:
    return any(marker in item for marker in ANTI_GHOSTWRITING_MARKERS)


def build_validated_feedback_from_sections(
    sections: Mapping[str, Sequence[str]] | Sequence[FeedbackSectionPreview],
) -> EssayFeedback:
    if isinstance(sections, Mapping):
        section_map = {name: list(items) for name, items in sections.items()}
    else:
        section_map = {section.section: list(section.items) for section in sections}

    missing = [section for section in SECTION_ORDER if section not in section_map]
    if missing:
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", f"missing sections: {missing}")

    revision_tasks = []
    for item in section_map["revision_tasks"]:
        parts = item.split(" | ", 1)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", "invalid revision task")
        revision_tasks.append({"instruction": parts[0].strip(), "target": parts[1].strip()})

    try:
        return EssayFeedback(
            strengths=section_map["strengths"],
            improvements=section_map["improvements"],
            problem_monsters=section_map["problem_monsters"],
            sentence_notes=section_map["sentence_notes"],
            revision_tasks=revision_tasks,
        )
    except ValidationError as exc:
        raise StreamSectionError("STREAM_FINAL_SCHEMA_INVALID", str(exc)) from exc
