import pytest

from app.services.essay_feedback_streaming import (
    EssayFeedbackSectionParser,
    StreamSectionError,
    build_validated_feedback_from_sections,
)
from app.services.llm_contracts import EssayFeedback


def test_parser_emits_validated_sections_only_after_closing_tag():
    parser = EssayFeedbackSectionParser()

    assert parser.feed("<strengths>\n- 能写清楚发生了什么") == []
    sections = parser.feed("\n- 有一处心情表达\n</strengths>")

    assert len(sections) == 1
    assert sections[0].section == "strengths"
    assert sections[0].items == ["能写清楚发生了什么", "有一处心情表达"]


def test_parser_rejects_out_of_order_section():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("<improvements>\n- 第二段缺少动作\n</improvements>")

    assert exc.value.code == "STREAM_SECTION_OUT_OF_ORDER"


def test_parser_rejects_duplicate_section():
    parser = EssayFeedbackSectionParser()
    parser.feed("<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>")

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("<strengths>\n- 重复内容\n- 重复内容\n</strengths>")

    assert exc.value.code == "STREAM_SECTION_DUPLICATE"


def test_parser_rejects_prose_outside_tags():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("我先来说两句\n<strengths>\n- 能写清楚发生了什么\n</strengths>")

    assert exc.value.code == "STREAM_SECTION_OUT_OF_ORDER"


def test_parser_rejects_prose_only_chunk_outside_tags():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("我先说")

    assert exc.value.code == "STREAM_SECTION_OUT_OF_ORDER"


def test_parser_waits_for_partial_opening_tag_prefix():
    parser = EssayFeedbackSectionParser()

    assert parser.feed("<str") == []
    sections = parser.feed("engths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>")

    assert len(sections) == 1
    assert sections[0].section == "strengths"


def test_parser_rejects_trailing_prose_after_final_section_as_out_of_order():
    parser = EssayFeedbackSectionParser()
    parser.feed("<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>")
    parser.feed("<improvements>\n- 第二段缺少动作\n</improvements>")
    parser.feed("<problem_monsters>\n- 细节缺口\n</problem_monsters>")
    parser.feed("<sentence_notes>\n- 把心情换成看到听到的细节\n</sentence_notes>")

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("<revision_tasks>\n- 给第二段加一个动作描写 | 第二段\n</revision_tasks>多说一句")

    assert exc.value.code == "STREAM_SECTION_OUT_OF_ORDER"


def test_parser_rejects_markdown_code_fence():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("```xml\n<strengths>\n- 能写清楚发生了什么\n</strengths>\n```")

    assert exc.value.code == "STREAM_FINAL_SCHEMA_INVALID"


def test_parser_rejects_nested_section_tags():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed(
            "<strengths>\n"
            "- 能写清楚发生了什么\n"
            "<improvements>\n- 第二段缺少动作\n</improvements>\n"
            "</strengths>"
        )

    assert exc.value.code == "STREAM_FINAL_SCHEMA_INVALID"


def test_parser_rejects_section_too_large():
    parser = EssayFeedbackSectionParser(max_buffer_bytes=40)

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("<strengths>\n- " + "很长" * 30)

    assert exc.value.code == "STREAM_SECTION_TOO_LARGE"


def test_parser_rejects_too_many_or_too_long_items():
    parser = EssayFeedbackSectionParser(max_item_chars=12)

    with pytest.raises(StreamSectionError) as exc:
        parser.feed(
            "<strengths>\n"
            "- 这句话明显超过限制\n"
            "- 有一处心情表达\n"
            "</strengths>"
        )

    assert exc.value.code == "STREAM_FINAL_SCHEMA_INVALID"


def test_parser_rejects_too_few_items():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("<strengths>\n- 能写清楚发生了什么\n</strengths>")

    assert exc.value.code == "STREAM_FINAL_SCHEMA_INVALID"


def test_parser_rejects_too_many_items():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed(
            "<strengths>\n"
            "- 能写清楚发生了什么\n"
            "- 有一处心情表达\n"
            "- 能按顺序写\n"
            "</strengths>"
        )

    assert exc.value.code == "STREAM_FINAL_SCHEMA_INVALID"


def test_parser_rejects_copy_ready_essay_body():
    parser = EssayFeedbackSectionParser()

    with pytest.raises(StreamSectionError) as exc:
        parser.feed(
            "<strengths>\n"
            "- 范文：今天阳光明媚，我走进校园，看见同学们在操场上奔跑。\n"
            "- 有一处心情表达\n"
            "</strengths>"
        )

    assert exc.value.code == "STREAM_ANTI_GHOSTWRITING_BLOCKED"


def test_problem_monsters_are_parsed_without_preview_frame():
    parser = EssayFeedbackSectionParser()

    assert parser.feed("<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>")
    assert parser.feed("<improvements>\n- 第二段缺少动作\n</improvements>")
    previews = parser.feed("<problem_monsters>\n- 细节缺口\n</problem_monsters>")

    assert previews == []
    assert parser.sections["problem_monsters"] == ["细节缺口"]


def test_mutating_preview_items_does_not_mutate_canonical_feedback():
    parser = EssayFeedbackSectionParser()

    previews = parser.feed("<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>")
    previews[0].items[0] = "被外部修改了"
    parser.feed("<improvements>\n- 第二段缺少动作\n</improvements>")
    parser.feed("<problem_monsters>\n- 细节缺口\n</problem_monsters>")
    parser.feed("<sentence_notes>\n- 把心情换成看到听到的细节\n</sentence_notes>")
    parser.feed("<revision_tasks>\n- 给第二段加一个动作描写 | 第二段\n</revision_tasks>")

    feedback = parser.build_feedback()

    assert feedback.strengths[0] == "能写清楚发生了什么"


def test_build_validated_feedback_from_sections_converts_revision_task():
    feedback = build_validated_feedback_from_sections(
        {
            "strengths": ["能写清楚发生了什么", "有一处心情表达"],
            "improvements": ["第二段缺少动作"],
            "problem_monsters": ["细节缺口"],
            "sentence_notes": ["把心情换成看到听到的细节"],
            "revision_tasks": ["给第二段加一个动作描写 | 第二段"],
        }
    )

    assert isinstance(feedback, EssayFeedback)
    assert feedback.revision_tasks[0].instruction == "给第二段加一个动作描写"
    assert feedback.revision_tasks[0].target == "第二段"


def test_parser_rejects_revision_task_without_pipe():
    parser = EssayFeedbackSectionParser()
    parser.feed("<strengths>\n- 能写清楚发生了什么\n- 有一处心情表达\n</strengths>")
    parser.feed("<improvements>\n- 第二段缺少动作\n</improvements>")
    parser.feed("<problem_monsters>\n- 细节缺口\n</problem_monsters>")
    parser.feed("<sentence_notes>\n- 把心情换成看到听到的细节\n</sentence_notes>")

    with pytest.raises(StreamSectionError) as exc:
        parser.feed("<revision_tasks>\n- 给第二段加一个动作描写\n</revision_tasks>")

    assert exc.value.code == "STREAM_FINAL_SCHEMA_INVALID"
