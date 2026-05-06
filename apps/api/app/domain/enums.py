from enum import Enum


class StudentPersona(str, Enum):
    real_child = "real_child"
    vague_expression = "vague_expression"
    weak_structure = "weak_structure"
    weak_reading_summary = "weak_reading_summary"


class TaskType(str, Enum):
    assessment = "assessment"
    sentence = "sentence"
    essay = "essay"
    reading = "reading"
    report = "report"


class ReportType(str, Enum):
    stage = "stage"
    weekly = "weekly"


class BadgeCode(str, Enum):
    first_sentence_upgrade = "first_sentence_upgrade"
    first_revision = "first_revision"
    reading_transfer = "reading_transfer"
