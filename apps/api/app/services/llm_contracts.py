from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

ChallengeSkill = Literal["expand_sentence", "action_expression", "feeling"]
ChallengeFocus = Literal["扩句", "动作描写", "心理感受"]
ChallengeGrade = Literal["三年级", "四年级", "五年级", "六年级"]
DifficultyLabel = Literal[
    "三年级基础",
    "三年级进阶",
    "四年级基础",
    "四年级进阶",
    "五年级基础",
    "五年级进阶",
    "六年级基础",
    "六年级进阶",
]


class RevisionTask(BaseModel):
    instruction: NonBlankStr
    target: NonBlankStr


class EssayFeedback(BaseModel):
    strengths: list[NonBlankStr] = Field(min_length=2, max_length=2)
    improvements: list[NonBlankStr] = Field(min_length=1, max_length=3)
    problem_monsters: list[NonBlankStr] = Field(min_length=1, max_length=3)
    sentence_notes: list[NonBlankStr] = Field(min_length=1, max_length=3)
    revision_tasks: list[RevisionTask] = Field(min_length=1, max_length=1)


class EssayRevisionComparison(BaseModel):
    encouragement: NonBlankStr
    improved_dimensions: list[NonBlankStr] = Field(min_length=1, max_length=3)
    evidence: list[NonBlankStr] = Field(min_length=1, max_length=3)
    next_step: NonBlankStr


class SentenceFeedback(BaseModel):
    encouragement: NonBlankStr
    specific_improvement: NonBlankStr
    next_step: NonBlankStr
    ability_delta: dict[str, int]
    problem_monsters: list[NonBlankStr] = Field(min_length=1, max_length=3)


class SentenceChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_sentence: NonBlankStr = Field(min_length=5, max_length=25)
    challenge_prompt: NonBlankStr = Field(min_length=10, max_length=60)
    hint: NonBlankStr = Field(min_length=10, max_length=80)
    target_skill: ChallengeSkill
    focus: ChallengeFocus
    difficulty_label: DifficultyLabel
    grade_label: ChallengeGrade


class SentenceChallengeFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encouragement: NonBlankStr = Field(min_length=8, max_length=30)
    highlight: NonBlankStr = Field(min_length=10, max_length=60)
    suggestion: NonBlankStr = Field(min_length=10, max_length=60)
    example_upgrade: NonBlankStr = Field(min_length=10, max_length=80)


class GhostwritingCheck(BaseModel):
    blocked: bool
    message: str
    next_question: str

    @model_validator(mode="after")
    def require_coaching_text_when_blocked(self) -> "GhostwritingCheck":
        if self.blocked and (not self.message.strip() or not self.next_question.strip()):
            raise ValueError("blocked ghostwriting checks require coaching text")
        return self


class MaterialQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: NonBlankStr
    hint: NonBlankStr


class MaterialCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[MaterialQuestion] = Field(min_length=3, max_length=5)
    encouragement: NonBlankStr


class OutlineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[NonBlankStr] = Field(min_length=3, max_length=5)
    tip: NonBlankStr


class ReportContent(BaseModel):
    practice_summary: NonBlankStr
    ability_changes: list[NonBlankStr] = Field(min_length=1, max_length=6)
    best_revision: NonBlankStr
    weak_points: list[NonBlankStr] = Field(min_length=1, max_length=2)
    next_suggestions: list[NonBlankStr] = Field(min_length=1, max_length=3)
