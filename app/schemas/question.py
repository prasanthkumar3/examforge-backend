from pydantic import BaseModel, Field, model_validator


QUESTION_TYPES = {
    "MCQ",
    "MULTIPLE_SELECT",
    "TRUE_FALSE",
    "SHORT_ANSWER",
}

DIFFICULTIES = {
    "EASY",
    "MEDIUM",
    "HARD",
}


class QuestionOptionCreate(BaseModel):
    option_text: str = Field(
        min_length=1,
        max_length=1000
    )

    is_correct: bool = False

    option_order: int = Field(
        ge=1
    )


class QuestionCreateRequest(BaseModel):
    question_text: str = Field(
        min_length=5,
        max_length=5000
    )

    question_type: str

    topic: str = Field(
        min_length=1,
        max_length=100
    )

    difficulty: str = "MEDIUM"

    explanation: str | None = None

    marks: int = Field(
        gt=0
    )

    negative_marks: int = Field(
        ge=0
    )

    options: list[QuestionOptionCreate] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_question(self):
        # Validate question type
        if self.question_type not in QUESTION_TYPES:
            raise ValueError(
                "question_type must be MCQ, MULTIPLE_SELECT, "
                "TRUE_FALSE, or SHORT_ANSWER"
            )

        # Validate difficulty
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(
                "difficulty must be EASY, MEDIUM, or HARD"
            )

        # MCQ
        if self.question_type == "MCQ":
            if len(self.options) < 2:
                raise ValueError(
                    "MCQ must have at least 2 options"
                )

            correct_count = sum(
                option.is_correct
                for option in self.options
            )

            if correct_count != 1:
                raise ValueError(
                    "MCQ must have exactly one correct option"
                )

        # Multiple select
        elif self.question_type == "MULTIPLE_SELECT":
            if len(self.options) < 2:
                raise ValueError(
                    "MULTIPLE_SELECT must have at least 2 options"
                )

            correct_count = sum(
                option.is_correct
                for option in self.options
            )

            if correct_count < 1:
                raise ValueError(
                    "MULTIPLE_SELECT must have at least one correct option"
                )

        # True / False
        elif self.question_type == "TRUE_FALSE":
            if len(self.options) != 2:
                raise ValueError(
                    "TRUE_FALSE must have exactly 2 options"
                )

            correct_count = sum(
                option.is_correct
                for option in self.options
            )

            if correct_count != 1:
                raise ValueError(
                    "TRUE_FALSE must have exactly one correct option"
                )

        # Short answer
        elif self.question_type == "SHORT_ANSWER":
            if self.options:
                raise ValueError(
                    "SHORT_ANSWER cannot have options"
                )

        # Prevent duplicate option ordering
        option_orders = [
            option.option_order
            for option in self.options
        ]

        if len(option_orders) != len(set(option_orders)):
            raise ValueError(
                "option_order values must be unique"
            )

        return self

class QuestionUpdateRequest(BaseModel):
    question_text: str | None = Field(
        default=None,
        min_length=5,
        max_length=5000
    )

    topic: str | None = Field(
        default=None,
        min_length=1,
        max_length=100
    )

    difficulty: str | None = None

    explanation: str | None = None

    marks: int | None = Field(
        default=None,
        gt=0
    )

    negative_marks: int | None = Field(
        default=None,
        ge=0
    )

    options: list[QuestionOptionCreate] | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if self.difficulty is not None:
            if self.difficulty not in DIFFICULTIES:
                raise ValueError(
                    "difficulty must be EASY, MEDIUM, or HARD"
                )

        if self.options is not None:
            option_orders = [
                option.option_order
                for option in self.options
            ]

            if len(option_orders) != len(set(option_orders)):
                raise ValueError(
                    "option_order values must be unique"
                )

        return self

class QuestionRejectRequest(BaseModel):
    reason: str = Field(
        min_length=3,
        max_length=1000
    )

class QuestionReviewResponse(BaseModel):
    id: str
    question_id: str
    reviewer_id: str
    action: str
    reason: str | None
    reviewed_at: object

class QuestionOptionResponse(BaseModel):
    id: str
    option_text: str
    is_correct: bool
    option_order: int


class QuestionResponse(BaseModel):
    id: str
    question_text: str
    question_type: str
    topic: str
    difficulty: str
    explanation: str | None
    marks: int
    negative_marks: int
    created_by: str
    status: str
    options: list[QuestionOptionResponse]
    created_at: object
    updated_at: object