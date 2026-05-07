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
                title="鍏ラ棬灏忚瘯鐐?",
                focus="绗竴寮犺兘鍔涜崏鍥?",
                minutes="3-5",
            ),
            quick=RecommendedTask(
                kind="sentence",
                title="鍙ュ瓙宸ュ潑",
                focus="鍔犵粏鑺?",
                minutes="5-8",
            ),
        )
    essay_focus = "鎶婇€夋潗鍜岀粨鏋勮娓呮" if ability.structure < 40 else "鎶婄粏鑺傚啓鍏蜂綋"
    sentence_focus = "鍔犲姩浣滄垨绁炴€?" if ability.observation < ability.expression else "鍔犵粏鑺?"
    return TodayTasks(
        main=RecommendedTask(kind="essay", title="浣滄枃鍩庡牎", focus=essay_focus, minutes="10-15"),
        quick=RecommendedTask(
            kind="sentence",
            title="鍙ュ瓙宸ュ潑",
            focus=sentence_focus,
            minutes="5-8",
        ),
    )
