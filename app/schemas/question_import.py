from datetime import datetime

from pydantic import BaseModel, Field


class ParsedQuestionOption(BaseModel):
    option_text: str
    option_order: int


class ParsedQuestion(BaseModel):
    question_text: str
    options: list[ParsedQuestionOption]

    correct_answers: list[int]

    topic: str = "General"
    difficulty: str = "MEDIUM"
    marks: int = Field(default=1, gt=0)
    negative_marks: int = Field(default=0, ge=0)


class QuestionPasteImportRequest(BaseModel):
    text: str = Field(
        min_length=10,
        max_length=100000
    )


class ImportedQuestionResponse(ParsedQuestion):
    id: str
    status: str


class QuestionPasteImportResponse(BaseModel):
    questions: list[ImportedQuestionResponse]
    total_questions: int