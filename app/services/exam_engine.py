from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.attempt_answer import AttemptAnswer
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt
from app.models.exam_question import ExamQuestion
from app.models.question import Question
from app.models.question_option import QuestionOption


OBJECTIVE_TYPES = {"MCQ", "MULTIPLE_SELECT", "TRUE_FALSE"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def attempt_deadline(exam: Exam, attempt: ExamAttempt) -> datetime:
    started = attempt.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return started + timedelta(minutes=exam.duration_minutes)


def expire_if_needed(db: Session, exam: Exam, attempt: ExamAttempt) -> bool:
    if attempt.status != "IN_PROGRESS":
        return False

    now = utc_now()
    end_at = exam.end_at
    if end_at is not None and end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)

    if now >= attempt_deadline(exam, attempt) or (end_at is not None and now >= end_at):
        attempt.status = "EXPIRED"
        attempt.submitted_at = now
        db.commit()
        return True
    return False


def ensure_attempt_active(db: Session, exam: Exam, attempt: ExamAttempt) -> None:
    if expire_if_needed(db, exam, attempt):
        raise HTTPException(status_code=400, detail="Exam attempt has expired")
    if attempt.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Exam attempt is no longer active")


def validate_exam_window(exam: Exam) -> None:
    now = utc_now()
    if exam.start_at is not None:
        start_at = exam.start_at
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        if now < start_at:
            raise HTTPException(status_code=400, detail="Exam has not started yet")
    if exam.end_at is not None:
        end_at = exam.end_at
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        if now >= end_at:
            raise HTTPException(status_code=400, detail="Exam has ended")


def validate_selected_options(
    db: Session,
    question: Question,
    selected_option_ids: Iterable[str],
) -> list:
    selected = list(dict.fromkeys(selected_option_ids))
    if question.question_type == "SHORT_ANSWER":
        if selected:
            raise HTTPException(status_code=400, detail="SHORT_ANSWER questions do not accept option IDs")
        return []

    options = db.query(QuestionOption).filter(QuestionOption.question_id == question.id).all()
    valid_ids = {str(option.id) for option in options}
    invalid = [option_id for option_id in selected if option_id not in valid_ids]
    if invalid:
        raise HTTPException(status_code=400, detail="One or more selected options do not belong to this question")

    if question.question_type == "MCQ" and len(selected) > 1:
        raise HTTPException(status_code=400, detail="MCQ accepts only one selected option")
    if question.question_type == "TRUE_FALSE" and len(selected) > 1:
        raise HTTPException(status_code=400, detail="TRUE_FALSE accepts only one selected option")
    return selected


def score_answer(
    question: Question,
    options: list[QuestionOption],
    selected_option_ids: Iterable[str],
    marks: int,
    negative_marks: int,
) -> int:
    selected = {str(option_id) for option_id in selected_option_ids}
    if not selected:
        return 0

    correct = {str(option.id) for option in options if option.is_correct}
    if question.question_type == "SHORT_ANSWER":
        raise HTTPException(
            status_code=400,
            detail="SHORT_ANSWER questions require manual grading and are not supported for automatic scoring yet",
        )

    return marks if selected == correct else -negative_marks


def calculate_score(db: Session, attempt: ExamAttempt) -> int:
    rows = (
        db.query(AttemptAnswer, ExamQuestion, Question)
        .join(ExamQuestion, ExamQuestion.question_id == AttemptAnswer.question_id)
        .join(Question, Question.id == AttemptAnswer.question_id)
        .filter(
            AttemptAnswer.attempt_id == attempt.id,
            ExamQuestion.exam_id == attempt.exam_id,
        )
        .all()
    )

    total = 0
    for answer, exam_question, question in rows:
        options = (
            db.query(QuestionOption)
            .filter(QuestionOption.question_id == question.id)
            .all()
        )
        total += score_answer(
            question,
            options,
            answer.selected_option_ids,
            exam_question.marks,
            exam_question.negative_marks,
        )
    return total
