from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ExamCreateRequest(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=200
    )

    description: str | None = None

    instructions: str | None = None

    exam_type: str = Field(
        description="COMMON, BATCH, or BOTH"
    )

    room_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=50
    )

    duration_minutes: int = Field(
        gt=0,
        le=1440
    )

    start_at: datetime | None = None

    end_at: datetime | None = None

    max_attempts: int = Field(
        default=1,
        ge=1
    )

    batch_codes: list[str] = Field(
        default_factory=list
    )

    completion_target: int | None = Field(
        default=None,
        gt=0
    )

    auto_close_on_target: bool = False

    @model_validator(mode="after")
    def validate_exam(self):

        if self.exam_type not in {
            "COMMON",
            "BATCH",
            "BOTH"
        }:
            raise ValueError(
                "exam_type must be COMMON, BATCH, or BOTH"
            )

        # -------------------------------------------------
        # COMMON
        # -------------------------------------------------

        if self.exam_type == "COMMON":

            if not self.room_code:
                raise ValueError(
                    "room_code is required for COMMON exams"
                )

            if self.batch_codes:
                raise ValueError(
                    "COMMON exams cannot have batch_codes"
                )

        # -------------------------------------------------
        # BATCH
        # -------------------------------------------------

        if self.exam_type == "BATCH":

            if self.room_code:
                raise ValueError(
                    "BATCH exams cannot have a room_code"
                )

            if not self.batch_codes:
                raise ValueError(
                    "At least one batch is required for BATCH exams"
                )

        # -------------------------------------------------
        # BOTH
        # -------------------------------------------------

        if self.exam_type == "BOTH":

            if not self.room_code:
                raise ValueError(
                    "room_code is required for BOTH exams"
                )

            if not self.batch_codes:
                raise ValueError(
                    "At least one batch is required for BOTH exams"
                )

        # -------------------------------------------------
        # Schedule validation
        # -------------------------------------------------

        if self.start_at and self.end_at:

            if self.end_at <= self.start_at:
                raise ValueError(
                    "end_at must be after start_at"
                )

        # -------------------------------------------------
        # Completion target
        # -------------------------------------------------

        if self.auto_close_on_target and not self.completion_target:
            raise ValueError(
                "completion_target is required when "
                "auto_close_on_target is enabled"
            )

        return self  
    
class ExamResponse(BaseModel):
    id: str
    title: str
    description: str | None
    instructions: str | None
    exam_type: str
    room_code: str | None
    duration_minutes: int
    start_at: datetime | None
    end_at: datetime | None
    max_attempts: int

    completion_target: int | None
    auto_close_on_target: bool

    created_by: str
    status: str
    created_at: datetime
    updated_at: datetime

class ExamUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    instructions: str | None = None
    exam_type: str | None = None
    room_code: str | None = Field(default=None, min_length=3, max_length=50)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    start_at: datetime | None = None
    end_at: datetime | None = None
    max_attempts: int | None = Field(default=None, ge=1)
    batch_codes: list[str] | None = None
    completion_target: int | None = Field(default=None, gt=0)
    auto_close_on_target: bool | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if self.exam_type is not None and self.exam_type not in {"COMMON", "BATCH", "BOTH"}:
            raise ValueError("exam_type must be COMMON, BATCH, or BOTH")
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        if self.auto_close_on_target is True and self.completion_target is None:
            raise ValueError("completion_target is required when auto_close_on_target is enabled")
        return self

class ExamQuestionCreateRequest(BaseModel):
    question_id: str
    question_order: int = Field(gt=0)
    marks: int = Field(gt=0)
    negative_marks: int = Field(ge=0)

class ExamQuestionOrderItem(BaseModel):
    question_id: str
    question_order: int = Field(gt=0)


class ExamQuestionReorderRequest(BaseModel):
    questions: list[ExamQuestionOrderItem]
    
class ExamQuestionUpdateRequest(BaseModel):
    marks: int = Field(gt=0)
    negative_marks: int = Field(ge=0)