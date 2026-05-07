from pydantic import BaseModel, Field, field_validator


class RevisionTask(BaseModel):
    instruction: str
    target: str


class EssayFeedback(BaseModel):
    strengths: list[str] = Field(min_length=2, max_length=2)
    improvements: list[str] = Field(min_length=1, max_length=3)
    problem_monsters: list[str] = Field(min_length=1, max_length=3)
    sentence_notes: list[str] = Field(min_length=1, max_length=3)
    revision_tasks: list[RevisionTask] = Field(min_length=1, max_length=3)


class SentenceFeedback(BaseModel):
    encouragement: str
    specific_improvement: str
    next_step: str
    ability_delta: dict[str, int]
    problem_monsters: list[str] = Field(min_length=1, max_length=3)


class GhostwritingCheck(BaseModel):
    blocked: bool
    message: str
    next_question: str


class ReportContent(BaseModel):
    practice_summary: str
    ability_changes: list[str] = Field(min_length=1, max_length=6)
    best_revision: str
    weak_points: list[str] = Field(min_length=1, max_length=2)
    next_suggestions: list[str] = Field(min_length=1, max_length=3)

    @field_validator("practice_summary", "best_revision")
    @classmethod
    def reject_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value
