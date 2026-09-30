from pydantic import BaseModel


class StudentExamOptionResponse(BaseModel):
    id: str
    option_text: str
    option_order: int


class StudentExamQuestionResponse(BaseModel):
    id: str
    question_text: str
    question_type: str
    question_order: int
    marks: int
    negative_marks: int
    options: list[StudentExamOptionResponse]


class StudentExamResponse(BaseModel):
    attempt_id: str
    exam_id: str
    title: str
    instructions: str | None
    duration_minutes: int
    started_at: str
    deadline_at: str
    remaining_seconds: int
    questions: list[StudentExamQuestionResponse]
    total_questions: int
