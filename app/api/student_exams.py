from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_optional_user
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt
from app.models.exam_question import ExamQuestion
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.user import User
from app.schemas.student_exam import (
    StudentExamOptionResponse,
    StudentExamQuestionResponse,
    StudentExamResponse,
)
from app.services.exam_engine import attempt_deadline, ensure_attempt_active

router = APIRouter(prefix="/student-exams", tags=["Student Exams"])


@router.get("/{attempt_id}/questions", response_model=StudentExamResponse)
def get_student_exam_questions(
    attempt_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found")

    if attempt.user_id is not None:
        if current_user is None or attempt.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not allowed to access this attempt")
    elif attempt.access_method != "ROOM_CODE":
        raise HTTPException(status_code=403, detail="You are not allowed to access this attempt")

    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.status != "PUBLISHED":
        raise HTTPException(status_code=400, detail="Exam is no longer available")

    ensure_attempt_active(db, exam, attempt)

    exam_questions = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id
    ).order_by(ExamQuestion.question_order).all()
    if not exam_questions:
        raise HTTPException(status_code=400, detail="This exam does not contain any questions")

    questions = []
    for exam_question in exam_questions:
        question = db.query(Question).filter(Question.id == exam_question.question_id).first()
        if not question:
            continue
        options = db.query(QuestionOption).filter(
            QuestionOption.question_id == question.id
        ).order_by(QuestionOption.option_order).all()
        questions.append(StudentExamQuestionResponse(
            id=str(question.id),
            question_text=question.question_text,
            question_type=question.question_type,
            question_order=exam_question.question_order,
            marks=exam_question.marks,
            negative_marks=exam_question.negative_marks,
            options=[
                StudentExamOptionResponse(
                    id=str(option.id),
                    option_text=option.option_text,
                    option_order=option.option_order,
                ) for option in options
            ],
        ))

    if not questions:
        raise HTTPException(status_code=400, detail="No valid questions are available for this exam")

    deadline = attempt_deadline(exam, attempt)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    remaining = max(0, int((deadline - __import__('datetime').datetime.now(timezone.utc)).total_seconds()))

    return StudentExamResponse(
        attempt_id=str(attempt.id),
        exam_id=str(exam.id),
        title=exam.title,
        instructions=exam.instructions,
        duration_minutes=exam.duration_minutes,
        started_at=attempt.started_at.isoformat(),
        deadline_at=deadline.isoformat(),
        remaining_seconds=remaining,
        questions=questions,
        total_questions=len(questions),
    )
