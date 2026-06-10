from dataclasses import dataclass

from app.services.llm_contracts import SentenceChallenge, SentenceChallengeFeedback


@dataclass(frozen=True)
class ChallengeTypeSpec:
    target_skill: str
    focus: str
    prompt: str
    hint: str
    ability_delta: dict[str, int]


CHALLENGE_TYPE_SPECS = {
    "expand_sentence": ChallengeTypeSpec(
        target_skill="expand_sentence",
        focus="扩句",
        prompt="请把句子写具体，补充时间、地点或样子。",
        hint="可以想一想谁在什么地方，看到或听到了什么。",
        ability_delta={"expression": 2, "observation": 2},
    ),
    "action_expression": ChallengeTypeSpec(
        target_skill="action_expression",
        focus="动作描写",
        prompt="请把句子写具体，加上动作和样子。",
        hint="可以写小猫怎么跑、跑到哪里、看起来怎么样。",
        ability_delta={"expression": 3, "observation": 2},
    ),
    "feeling": ChallengeTypeSpec(
        target_skill="feeling",
        focus="心理感受",
        prompt="请把句子写具体，加上一点心里想法。",
        hint="可以写人物当时在想什么，心情有什么变化。",
        ability_delta={"expression": 2, "observation": 1},
    ),
}


FALLBACK_SOURCE_SENTENCES = {
    "expand_sentence": "小花开了。",
    "action_expression": "小猫跑了。",
    "feeling": "我走进教室。",
}


def deterministic_challenge_ability_delta(target_skill: str) -> dict[str, int]:
    return dict(CHALLENGE_TYPE_SPECS[target_skill].ability_delta)


def fallback_challenge(target_skill: str) -> SentenceChallenge:
    spec = CHALLENGE_TYPE_SPECS[target_skill]
    return SentenceChallenge(
        source_sentence=FALLBACK_SOURCE_SENTENCES[target_skill],
        challenge_prompt=spec.prompt,
        hint=spec.hint,
        target_skill=spec.target_skill,
        focus=spec.focus,
        difficulty_label="四年级基础",
        grade_label="四年级",
    )


def fallback_challenge_feedback(target_skill: str) -> SentenceChallengeFeedback:
    if target_skill == "feeling":
        return SentenceChallengeFeedback(
            encouragement="你把心情写出来了！",
            highlight="你写出了人物心里的想法。",
            suggestion="还可以加一个动作表现心情。",
            example_upgrade="我攥紧书包带，心里既紧张又期待。",
        )
    return SentenceChallengeFeedback(
        encouragement="你写得更具体了！",
        highlight="你给句子加上了清楚的细节。",
        suggestion="还可以再加一个看到的画面。",
        example_upgrade="小猫轻轻一跃，飞快地跑过草地。",
    )
