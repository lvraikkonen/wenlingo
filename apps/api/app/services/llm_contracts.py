from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator


NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RevisionTask(BaseModel):
    instruction: NonBlankStr
    target: NonBlankStr


class EssayFeedback(BaseModel):
    strengths: list[NonBlankStr] = Field(min_length=2, max_length=2)
    improvements: list[NonBlankStr] = Field(min_length=1, max_length=3)
    problem_monsters: list[NonBlankStr] = Field(min_length=1, max_length=3)
    sentence_notes: list[NonBlankStr] = Field(min_length=1, max_length=3)
    revision_tasks: list[RevisionTask] = Field(min_length=1, max_length=3)


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


class GhostwritingCheck(BaseModel):
    blocked: bool
    message: str
    next_question: str

    @model_validator(mode="after")
    def require_coaching_text_when_blocked(self) -> "GhostwritingCheck":
        if self.blocked and (not self.message.strip() or not self.next_question.strip()):
            raise ValueError("blocked ghostwriting checks require coaching text")
        return self


class ReportContent(BaseModel):
    practice_summary: NonBlankStr
    ability_changes: list[NonBlankStr] = Field(min_length=1, max_length=6)
    best_revision: NonBlankStr
    weak_points: list[NonBlankStr] = Field(min_length=1, max_length=2)
    next_suggestions: list[NonBlankStr] = Field(min_length=1, max_length=3)
