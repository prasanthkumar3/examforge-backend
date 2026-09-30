from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CommonExamAttemptRequest(BaseModel):
    room_code: str = Field(min_length=3, max_length=50)
    candidate_name: str = Field(min_length=2, max_length=150)
    candidate_email: str = Field(min_length=5, max_length=255)

    @field_validator("room_code", "candidate_name", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class AttemptAnswerRequest(BaseModel):
    selected_option_ids: list[str] = Field(default_factory=list)


class ExamAttemptResponse(BaseModel):
    id: str
    exam_id: str
    user_id: str | None
    access_method: str
    candidate_name: str | None
    candidate_email: str | None
    attempt_number: int
    status: str
    started_at: datetime
    submitted_at: datetime | None
    score: int | None
    created_at: datetime
    updated_at: datetime


class AttemptAnswerResponse(BaseModel):
    attempt_id: str
    question_id: str
    selected_option_ids: list[str]
    answered_at: datetime


class AttemptSubmitResponse(BaseModel):
    attempt_id: str
    status: str
    score: int | None
    submitted_at: datetime | None

class AttemptResultOptionResponse(BaseModel):
    id: str
    option_text: str
    option_order: int

class AttemptResultQuestionResponse(BaseModel):
    question_id: str
    question_order: int
    question_text: str
    question_type: str
    options: list[AttemptResultOptionResponse]
    selected_option_ids: list[str]
    correct_option_ids: list[str]
    marks: int
    negative_marks: int
    awarded_marks: int

class AttemptResultResponse(BaseModel):
    attempt_id: str
    exam_id: str
    status: str
    score: int | None
    total_questions: int
    answered_questions: int
    submitted_at: datetime | None
    questions: list[AttemptResultQuestionResponse]

class ExamAttemptSummaryResponse(BaseModel):
    id: str
    exam_id: str
    user_id: str | None
    candidate_name: str | None
    candidate_email: str | None
    attempt_number: int
    access_method: str
    status: str
    score: int | None
    started_at: datetime
    submitted_at: datetime | None
    

