from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

ChallengeSkill = Literal["expand_sentence", "action_expression", "feeling"]
ChallengeFocus = Literal["扩句", "动作描写", "心理感受"]
ChallengeGrade = Literal["三年级", "四年级", "五年级", "六年级"]
TopicCardKind = Literal["topic_question", "must_include", "shine_point"]
MaterialCardCategory = NonBlankStr
OutlineSlot = NonBlankStr
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


class TopicAnalysisCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankStr
    kind: TopicCardKind
    title: NonBlankStr = Field(max_length=16)
    body: NonBlankStr = Field(max_length=80)
    required_points: list[NonBlankStr] = Field(default_factory=list, max_length=3)


class WritingTopicAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[TopicAnalysisCard] = Field(min_length=3, max_length=3)
    suggested_focus: NonBlankStr = Field(max_length=80)


class MaterialQuestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankStr
    text: NonBlankStr = Field(max_length=60)
    hint: NonBlankStr = Field(max_length=80)
    order: int = Field(ge=1, le=3)


class MaterialQuestionsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[MaterialQuestionItem] = Field(min_length=3, max_length=3)
    encouragement: NonBlankStr = Field(max_length=40)


class MaterialCardSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankStr
    category: MaterialCardCategory
    text: str = Field(default="", max_length=120)
    source_answer_ids: list[NonBlankStr] = Field(default_factory=list, max_length=3)
    source_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=3)
    placeholder: bool = False

    @model_validator(mode="after")
    def require_source_for_non_placeholder(self) -> "MaterialCardSlot":
        if not self.placeholder and not self.source_answer_ids and not self.source_refs:
            raise ValueError("non-placeholder material cards require source refs")
        if self.placeholder and self.text and not self.source_answer_ids and not self.source_refs:
            raise ValueError("placeholder material cards without sources cannot contain story content")
        return self


class MaterialCardsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[MaterialCardSlot] = Field(min_length=1, max_length=8)
    encouragement: NonBlankStr = Field(max_length=40)


class WritingOutlineSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankStr
    slot: OutlineSlot
    heading: NonBlankStr = Field(max_length=12)
    note: str = Field(default="", max_length=80)
    source_card_ids: list[NonBlankStr] = Field(default_factory=list, max_length=3)
    placeholder: bool = False

    @model_validator(mode="after")
    def require_source_for_story_content(self) -> "WritingOutlineSection":
        if not self.placeholder and self.note.strip() and not self.source_card_ids:
            raise ValueError("story-specific outline sections require source_card_ids")
        return self


class WritingOutlineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[WritingOutlineSection] = Field(min_length=1, max_length=6)
    tip: NonBlankStr = Field(max_length=60)


class ReportContent(BaseModel):
    practice_summary: NonBlankStr
    ability_changes: list[NonBlankStr] = Field(min_length=1, max_length=6)
    best_revision: NonBlankStr
    weak_points: list[NonBlankStr] = Field(min_length=1, max_length=2)
    next_suggestions: list[NonBlankStr] = Field(min_length=1, max_length=3)
