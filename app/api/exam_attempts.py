from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_optional_user
from app.dependencies.roles import require_admin_or_examiner, require_student
from app.models.attempt_answer import AttemptAnswer
from app.models.batch_member import BatchMember
from app.models.exam import Exam
from app.models.exam_attempt import ExamAttempt
from app.models.exam_batch import ExamBatch
from app.models.exam_question import ExamQuestion
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.user import User
from app.schemas.exam_attempt import (
    AttemptAnswerRequest,
    AttemptAnswerResponse,
    AttemptResultQuestionResponse,
    AttemptResultResponse,
    AttemptSubmitResponse,
    CommonExamAttemptRequest,
    ExamAttemptResponse,
    ExamAttemptSummaryResponse,
    AttemptResultOptionResponse,
)
from app.services.exam_engine import (
    calculate_score,
    ensure_attempt_active,
    validate_exam_window,
    validate_selected_options,
)

router = APIRouter(prefix="/exam-attempts", tags=["Exam Attempts"])


def build_attempt_response(attempt: ExamAttempt) -> ExamAttemptResponse:
    return ExamAttemptResponse(
        id=str(attempt.id),
        exam_id=str(attempt.exam_id),
        user_id=str(attempt.user_id) if attempt.user_id else None,
        access_method=attempt.access_method,
        candidate_name=attempt.candidate_name,
        candidate_email=attempt.candidate_email,
        attempt_number=attempt.attempt_number,
        status=attempt.status,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
        score=attempt.score,
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )


def _check_target(db: Session, exam: Exam) -> None:
    if exam.auto_close_on_target and exam.completion_target is not None:
        completed_count = db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.status == "SUBMITTED",
        ).count()
        if completed_count >= exam.completion_target:
            raise HTTPException(status_code=400, detail="Exam completion target has been reached")


def _get_attempt_for_user(
    db: Session,
    attempt_id: str,
    user: User | None,
) -> ExamAttempt:

    attempt = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.id == attempt_id)
        .first()
    )

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail="Exam attempt not found",
        )

    if user is None:
        if attempt.access_method == "ROOM_CODE":
            return attempt

        raise HTTPException(
            status_code=403,
            detail="You are not allowed to access this attempt",
        )
    
    # Admin and Examiner can access every attempt
    if user and user.role in ("ADMIN", "EXAMINER"):
        return attempt

    # Student must own the attempt
    if user and user.role == "STUDENT":

        # Batch attempt → ownership through user_id
        if attempt.access_method == "BATCH":
            if attempt.user_id != user.id:
                raise HTTPException(
                    status_code=403,
                    detail="You are not allowed to access this attempt",
                )

            return attempt

        # Common / Room-code attempt → ownership through email
        if attempt.access_method == "ROOM_CODE":
            if not attempt.candidate_email:
                raise HTTPException(
                    status_code=403,
                    detail="You are not allowed to access this attempt",
                )

            if user.email.strip().lower() != attempt.candidate_email.strip().lower():
                raise HTTPException(
                    status_code=403,
                    detail="You are not allowed to access this attempt",
                )

            return attempt

    raise HTTPException(
        status_code=403,
        detail="You are not allowed to access this attempt",
    )

@router.post("/batch/{exam_id}", response_model=ExamAttemptResponse, status_code=status.HTTP_201_CREATED)
def start_batch_exam(
    exam_id: str,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if exam.status != "PUBLISHED":
        raise HTTPException(status_code=400, detail="Exam is not available")
    if exam.exam_type not in {"BATCH", "BOTH"}:
        raise HTTPException(status_code=403, detail="This exam does not allow batch access")

    eligible = db.query(ExamBatch).join(
        BatchMember, BatchMember.batch_id == ExamBatch.batch_id
    ).filter(
        ExamBatch.exam_id == exam.id,
        BatchMember.student_id == current_user.id,
        BatchMember.status == "ACTIVE",
    ).first()
    if not eligible:
        raise HTTPException(status_code=403, detail="You are not eligible for this exam")

    validate_exam_window(exam)
    _check_target(db, exam)

    active_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam.id,
        ExamAttempt.user_id == current_user.id,
        ExamAttempt.access_method == "BATCH",
        ExamAttempt.status == "IN_PROGRESS",
    ).first()
    if active_attempt:
        ensure_attempt_active(db, exam, active_attempt)
        return build_attempt_response(active_attempt)

    attempt_count = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam.id,
        ExamAttempt.user_id == current_user.id,
    ).count()
    if attempt_count >= exam.max_attempts:
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=current_user.id,
        access_method="BATCH",
        attempt_number=attempt_count + 1,
        status="IN_PROGRESS",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return build_attempt_response(attempt)


@router.post("/common", response_model=ExamAttemptResponse, status_code=status.HTTP_201_CREATED)
def start_common_exam(request: CommonExamAttemptRequest, db: Session = Depends(get_db)):
    email = request.candidate_email.strip().lower()
    exam = db.query(Exam).filter(Exam.room_code == request.room_code.strip()).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Invalid room code")
    if exam.status != "PUBLISHED":
        raise HTTPException(status_code=400, detail="Exam is not available")
    if exam.exam_type not in {"COMMON", "BOTH"}:
        raise HTTPException(status_code=403, detail="This exam does not allow room-code access")
    validate_exam_window(exam)
    _check_target(db, exam)

    active_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam.id,
        ExamAttempt.access_method == "ROOM_CODE",
        func.lower(ExamAttempt.candidate_email) == email,
        ExamAttempt.status == "IN_PROGRESS",
    ).first()
    if active_attempt:
        ensure_attempt_active(db, exam, active_attempt)
        return build_attempt_response(active_attempt)

    attempt_count = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam.id,
        ExamAttempt.access_method == "ROOM_CODE",
        func.lower(ExamAttempt.candidate_email) == email,
    ).count()
    if attempt_count >= exam.max_attempts:
        raise HTTPException(status_code=400, detail="Maximum attempts reached")

    attempt = ExamAttempt(
        exam_id=exam.id,
        access_method="ROOM_CODE",
        candidate_name=request.candidate_name,
        candidate_email=email,
        attempt_number=attempt_count + 1,
        status="IN_PROGRESS",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return build_attempt_response(attempt)


@router.put("/{attempt_id}/answers/{question_id}", response_model=AttemptAnswerResponse)
def save_answer(
    attempt_id: str,
    question_id: str,
    request: AttemptAnswerRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt_for_user(db, attempt_id, current_user)
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    ensure_attempt_active(db, exam, attempt)

    exam_question = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id,
        ExamQuestion.question_id == question_id,
    ).first()
    if not exam_question:
        raise HTTPException(status_code=404, detail="Question is not part of this exam")

    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    selected = validate_selected_options(db, question, request.selected_option_ids)
    answer = db.query(AttemptAnswer).filter(
        AttemptAnswer.attempt_id == attempt.id,
        AttemptAnswer.question_id == question.id,
    ).first()
    if answer:
        answer.selected_option_ids = selected
    else:
        answer = AttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_option_ids=selected,
        )
        db.add(answer)

    db.commit()
    db.refresh(answer)
    return AttemptAnswerResponse(
        attempt_id=str(answer.attempt_id),
        question_id=str(answer.question_id),
        selected_option_ids=[str(option_id) for option_id in answer.selected_option_ids],
        answered_at=answer.answered_at,
    )


@router.get("/{attempt_id}/answers", response_model=list[AttemptAnswerResponse])
def get_saved_answers(
    attempt_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt_for_user(db, attempt_id, current_user)
    answers = db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id == attempt.id).all()
    return [
        AttemptAnswerResponse(
            attempt_id=str(answer.attempt_id),
            question_id=str(answer.question_id),
            selected_option_ids=[str(value) for value in answer.selected_option_ids],
            answered_at=answer.answered_at,
        )
        for answer in answers
    ]


@router.post("/{attempt_id}/submit", response_model=AttemptSubmitResponse)
def submit_attempt(
    attempt_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt_for_user(db, attempt_id, current_user)
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    ensure_attempt_active(db, exam, attempt)

    score = calculate_score(db, attempt)
    attempt.score = score
    attempt.status = "SUBMITTED"
    from datetime import datetime, timezone
    attempt.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)

    if exam.auto_close_on_target and exam.completion_target is not None:
        completed_count = db.query(ExamAttempt).filter(
            ExamAttempt.exam_id == exam.id,
            ExamAttempt.status == "SUBMITTED",
        ).count()
        if completed_count >= exam.completion_target:
            exam.status = "CLOSED"
            db.commit()

    return AttemptSubmitResponse(
        attempt_id=str(attempt.id),
        status=attempt.status,
        score=attempt.score,
        submitted_at=attempt.submitted_at,
    )


@router.get("/my", response_model=list[ExamAttemptSummaryResponse])
def get_my_attempts(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.user_id == current_user.id
    ).order_by(ExamAttempt.created_at.desc()).all()
    return [
        ExamAttemptSummaryResponse(
            id=str(attempt.id),
            exam_id=str(attempt.exam_id),
            user_id=str(attempt.user_id) if attempt.user_id else None,
            candidate_name=attempt.candidate_name,
            candidate_email=attempt.candidate_email,
            attempt_number=attempt.attempt_number,
            access_method=attempt.access_method,
            status=attempt.status,
            score=attempt.score,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
        )
        for attempt in attempts
    ]


@router.get("/exam/{exam_id}/results", response_model=list[ExamAttemptSummaryResponse])
def get_exam_results(
    exam_id: str,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    from app.services.access import ensure_exam_access
    ensure_exam_access(exam, current_user)
    attempts = db.query(ExamAttempt).filter(
        ExamAttempt.exam_id == exam.id
    ).order_by(ExamAttempt.created_at.desc()).all()
    return [
        ExamAttemptSummaryResponse(
            id=str(attempt.id),
            exam_id=str(attempt.exam_id),
            user_id=str(attempt.user_id) if attempt.user_id else None,
            candidate_name=attempt.candidate_name,
            candidate_email=attempt.candidate_email,
            attempt_number=attempt.attempt_number,
            access_method=attempt.access_method,
            status=attempt.status,
            score=attempt.score,
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
        )
        for attempt in attempts
    ]

@router.get("/{attempt_id}/questions")
def get_attempt_questions(
    attempt_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------------
    # Get and validate the attempt
    # ---------------------------------------------------------
    attempt = _get_attempt_for_user(db, attempt_id, current_user)

    # ---------------------------------------------------------
    # Get the exam
    # ---------------------------------------------------------
    exam = (
        db.query(Exam)
        .filter(Exam.id == attempt.exam_id)
        .first()
    )

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    # ---------------------------------------------------------
    # Make sure the attempt is still active
    # This also handles exam expiration.
    # ---------------------------------------------------------
    if attempt.status == "IN_PROGRESS":
        ensure_attempt_active(db, exam, attempt)

    # ---------------------------------------------------------
    # Get questions assigned to this exam
    # ---------------------------------------------------------
    rows = (
        db.query(
            ExamQuestion,
            Question
        )
        .join(
            Question,
            ExamQuestion.question_id == Question.id
        )
        .filter(
            ExamQuestion.exam_id == exam.id
        )
        .order_by(
            ExamQuestion.question_order.asc()
        )
        .all()
    )

    # ---------------------------------------------------------
    # Get all options for these questions
    # IMPORTANT:
    # is_correct is intentionally NOT returned.
    # ---------------------------------------------------------
    question_ids = [
        question.id
        for _, question in rows
    ]

    options = []

    if question_ids:
        options = (
            db.query(QuestionOption)
            .filter(
                QuestionOption.question_id.in_(question_ids)
            )
            .order_by(
                QuestionOption.question_id.asc(),
                QuestionOption.option_order.asc()
            )
            .all()
        )

    # ---------------------------------------------------------
    # Group options by question
    # ---------------------------------------------------------
    options_by_question = {}

    for option in options:
        options_by_question.setdefault(
            option.question_id,
            []
        ).append(option)

    # ---------------------------------------------------------
    # Build safe student question response
    # ---------------------------------------------------------
    questions = []

    for exam_question, question in rows:

        questions.append({
            "question_id": str(question.id),
            "question_order": exam_question.question_order,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "topic": question.topic,
            "difficulty": question.difficulty,
            "marks": exam_question.marks,
            "negative_marks": exam_question.negative_marks,

            "options": [
                {
                    "id": str(option.id),
                    "option_text": option.option_text,
                    "option_order": option.option_order,
                }
                for option in options_by_question.get(
                    question.id,
                    []
                )
            ],
        })

    # ---------------------------------------------------------
    # Return exam + questions
    # ---------------------------------------------------------
    return {
        "attempt_id": str(attempt.id),
        "exam": {
            "id": str(exam.id),
            "title": exam.title,
            "instructions": exam.instructions,
            "duration_minutes": exam.duration_minutes,
        },
        "status": attempt.status,
        "total_questions": len(questions),
        "questions": questions,
    }

@router.get("/{attempt_id}", response_model=ExamAttemptResponse)
def get_attempt(
    attempt_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    attempt = _get_attempt_for_user(db, attempt_id, current_user)
    exam = db.query(Exam).filter(Exam.id == attempt.exam_id).first()
    if exam and attempt.status == "IN_PROGRESS":
        from app.services.exam_engine import expire_if_needed
        expire_if_needed(db, exam, attempt)
    return build_attempt_response(attempt)


@router.get("/{attempt_id}/result", response_model=AttemptResultResponse)
def get_attempt_result(
    attempt_id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------------
    # Get and authorize the attempt
    # ---------------------------------------------------------
    attempt = _get_attempt_for_user(
        db,
        attempt_id,
        current_user,
    )

    # ---------------------------------------------------------
    # Result can only be viewed after submission
    # ---------------------------------------------------------
    if attempt.status == "IN_PROGRESS":
        raise HTTPException(
            status_code=400,
            detail="Submit the exam before viewing the result",
        )

    # ---------------------------------------------------------
    # Get all questions belonging to this exam
    # in the exact order used by the exam
    # ---------------------------------------------------------
    exam_questions = (
        db.query(ExamQuestion)
        .filter(
            ExamQuestion.exam_id == attempt.exam_id
        )
        .order_by(
            ExamQuestion.question_order.asc()
        )
        .all()
    )

    # ---------------------------------------------------------
    # Get all answers submitted for this attempt
    # ---------------------------------------------------------
    answers = {
        str(answer.question_id): answer
        for answer in (
            db.query(AttemptAnswer)
            .filter(
                AttemptAnswer.attempt_id == attempt.id
            )
            .all()
        )
    }

    result_questions = []
    answered_count = 0

    # ---------------------------------------------------------
    # Build detailed result for every exam question
    # ---------------------------------------------------------
    for exam_question in exam_questions:

        question = (
            db.query(Question)
            .filter(
                Question.id == exam_question.question_id
            )
            .first()
        )

        if not question:
            continue

        # -----------------------------------------------------
        # Candidate's saved answer
        # -----------------------------------------------------
        answer = answers.get(str(question.id))

        selected = (
            [str(value) for value in answer.selected_option_ids]
            if answer
            else []
        )

        if selected:
            answered_count += 1

        # -----------------------------------------------------
        # Get ALL options for the question
        # -----------------------------------------------------
        options = (
            db.query(QuestionOption)
            .filter(
                QuestionOption.question_id == question.id
            )
            .order_by(
                QuestionOption.option_order.asc()
            )
            .all()
        )

        # -----------------------------------------------------
        # Correct options
        # -----------------------------------------------------
        correct = [
            str(option.id)
            for option in options
            if option.is_correct
        ]

        # -----------------------------------------------------
        # Calculate awarded marks
        # -----------------------------------------------------
        if not selected:
            awarded = 0

        elif set(selected) == set(correct):
            awarded = exam_question.marks

        else:
            awarded = -exam_question.negative_marks

        # -----------------------------------------------------
        # Add complete question result
        # -----------------------------------------------------
        result_questions.append(
            AttemptResultQuestionResponse(
                question_id=str(question.id),
                question_order=exam_question.question_order,
                question_text=question.question_text,
                question_type=question.question_type,

                options=[
                    AttemptResultOptionResponse(
                        id=str(option.id),
                        option_text=option.option_text,
                        option_order=option.option_order,
                    )
                    for option in options
                ],

                selected_option_ids=selected,
                correct_option_ids=correct,

                marks=exam_question.marks,
                negative_marks=exam_question.negative_marks,
                awarded_marks=awarded,
            )
        )

    # ---------------------------------------------------------
    # Return complete attempt result
    # ---------------------------------------------------------
    return AttemptResultResponse(
        attempt_id=str(attempt.id),
        exam_id=str(attempt.exam_id),
        status=attempt.status,
        score=attempt.score,
        total_questions=len(result_questions),
        answered_questions=answered_count,
        submitted_at=attempt.submitted_at,
        questions=result_questions,
    )