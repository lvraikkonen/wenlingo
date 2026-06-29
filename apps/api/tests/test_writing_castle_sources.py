import pytest

from app.services.writing_castle_sources import (
    normalize_source_refs,
    validate_expository_fact_sources,
)
from app.services.writing_castle_scaffold import resolve_scaffold_snapshot
from app.services.writing_castle_state import (
    attach_scaffold_snapshot,
    confirm_material_cards,
    init_material_card_state,
    init_outline_state,
    merge_material_answers,
)


def test_ai_suggestion_source_is_not_valid_content_source():
    with pytest.raises(ValueError, match="AI suggestion IDs alone are not valid sources"):
        normalize_source_refs([{"source_type": "ai_suggestion", "suggestion_id": "s1"}])


def test_source_refs_must_contain_objects():
    with pytest.raises(ValueError, match="source_refs must contain objects"):
        normalize_source_refs(["bad"])


def test_child_confirmed_source_is_valid():
    refs = normalize_source_refs(
        [
            {
                "source_type": "child_confirmed",
                "confirmation_id": "c1",
                "confirmed_text": "大熊猫主要吃竹子。",
                "original_suggestion_id": "s1",
            }
        ]
    )

    assert refs[0]["source_type"] == "child_confirmed"


def test_confirm_material_cards_accepts_child_confirmed_practical_content():
    scaffold = resolve_scaffold_snapshot("practical_writing", "letter", "manual")
    material = init_material_card_state()
    material, _outline = attach_scaffold_snapshot(material, init_outline_state(), scaffold)
    material = merge_material_answers(
        material,
        answers=[
            {"id": "answer-1", "question_id": "q-main", "text": "我想感谢老师鼓励我。", "skipped": False}
        ],
    )
    cards = [
        {
            "id": "card-main-message",
            "category": "main_message",
            "text": "我想感谢老师鼓励我。",
            "source_answer_ids": ["answer-1"],
            "source_refs": [
                {
                    "source_type": "child_confirmed",
                    "confirmation_id": "card-main-message",
                    "confirmed_text": "我想感谢老师鼓励我。",
                }
            ],
            "order": 1,
            "deleted": False,
            "child_edited": True,
            "placeholder": False,
        }
    ]

    saved = confirm_material_cards(material, cards, scaffold=scaffold)

    assert saved["cards"][0]["source_refs"][0]["source_type"] == "child_confirmed"


def test_topic_requirement_only_supports_explicit_fact():
    refs = [
        {
            "source_type": "topic_requirement",
            "topic_requirement_id": "topic",
            "quote_or_summary": "题目要求介绍国宝大熊猫。",
        }
    ]

    validate_expository_fact_sources("介绍国宝大熊猫", refs)
    with pytest.raises(ValueError, match="topic_requirement does not explicitly contain factual claim"):
        validate_expository_fact_sources("大熊猫主要吃竹子。", refs)


def test_reading_material_can_support_expository_fact():
    refs = [
        {
            "source_type": "reading_material",
            "reading_material_ref": "material-1",
            "quote_or_summary": "大熊猫主要吃竹子。",
        }
    ]

    validate_expository_fact_sources("大熊猫主要吃竹子。", refs)
