import pytest

from app.services.essay_feedback_streaming import (
    EssayFeedbackSectionParser,
    StreamSectionError,
)


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
