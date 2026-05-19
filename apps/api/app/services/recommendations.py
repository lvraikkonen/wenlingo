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


def choose_today_tasks(ability: AbilityProfile, has_completed_assessment: bool) -> TodayTasks:
    if not has_completed_assessment:
        return TodayTasks(
            main=RecommendedTask(
                kind="assessment",
                title="入门小试炼",
                focus="第一张能力草图",
                minutes="3-5",
            ),
            quick=RecommendedTask(
                kind="sentence",
                title="句子工坊",
                focus="加细节",
                minutes="5-8",
            ),
        )
    if ability.summarization < 35 or ability.comprehension < 35:
        essay_focus = "先把阅读内容概括清楚"
    elif ability.structure < 40:
        essay_focus = "把选材和结构说清楚"
    else:
        essay_focus = "把细节写具体"
    sentence_focus = "加动作或神态" if ability.observation < ability.expression else "加细节"
    return TodayTasks(
        main=RecommendedTask(kind="essay", title="作文城堡", focus=essay_focus, minutes="10-15"),
        quick=RecommendedTask(
            kind="sentence",
            title="句子工坊",
            focus=sentence_focus,
            minutes="5-8",
        ),
    )
