from pydantic import BaseModel

from app.domain.models import AbilityProfile


class RecommendedTask(BaseModel):
    kind: str
    title: str
    focus: str
    minutes: str


class TodayTasks(BaseModel):
    main: RecommendedTask
    quick: RecommendedTask


DEFAULT_ABILITY_VALUE = 40


def _is_default_ability_profile(ability: AbilityProfile) -> bool:
    return all(
        getattr(ability, name) == DEFAULT_ABILITY_VALUE
        for name in (
            "expression",
            "observation",
            "structure",
            "revision",
            "comprehension",
            "summarization",
        )
    )


def choose_today_tasks(ability: AbilityProfile) -> TodayTasks:
    sentence_focus = (
        "加动作或神态"
        if ability.observation < ability.expression or ability.expression < 35
        else "加细节"
    )
    quick = RecommendedTask(
        kind="sentence",
        title="句子工坊",
        focus=sentence_focus,
        minutes="5-8",
    )
    if _is_default_ability_profile(ability):
        return TodayTasks(
            main=RecommendedTask(
                kind="assessment",
                title="入门小试炼",
                focus="第一张能力草图",
                minutes="3-5",
            ),
            quick=quick,
        )
    if ability.comprehension < 35 or ability.summarization < 35:
        essay_focus = "先把阅读内容概括清楚"
    elif ability.structure < 40:
        essay_focus = "把选材和结构说清楚"
    elif ability.expression < 35 or ability.observation < 35:
        essay_focus = "把句子和细节写具体"
    else:
        essay_focus = "把细节写具体"
    return TodayTasks(
        main=RecommendedTask(kind="essay", title="作文城堡", focus=essay_focus, minutes="10-15"),
        quick=quick,
    )
