from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.roles import require_admin_or_examiner
from app.models.user import User
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.schemas.question import (
    QuestionCreateRequest,
    QuestionResponse,
    QuestionOptionResponse,
    QuestionUpdateRequest,
    QuestionOptionResponse,
    QuestionRejectRequest,
    QuestionReviewResponse
)
from app.models.question_review import QuestionReview

from app.schemas.question_import import (
    QuestionPasteImportRequest,
    QuestionPasteImportResponse,
    ImportedQuestionResponse
)

from app.services.question_parser import parse_questions


router = APIRouter(
    prefix="/api/questions",
    tags=["Question Bank"]
)


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_question(
    request: QuestionCreateRequest,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    question = Question(
        question_text=request.question_text,
        question_type=request.question_type,
        topic=request.topic,
        difficulty=request.difficulty,
        explanation=request.explanation,
        marks=request.marks,
        negative_marks=request.negative_marks,
        created_by=current_user.id,
        status="DRAFT",
    )

    db.add(question)
    db.flush()

    for option in request.options:
        question_option = QuestionOption(
            question_id=question.id,
            option_text=option.option_text,
            is_correct=option.is_correct,
            option_order=option.option_order,
        )

        db.add(question_option)

    db.commit()
    db.refresh(question)

    options = (
        db.query(QuestionOption)
        .filter(QuestionOption.question_id == question.id)
        .order_by(QuestionOption.option_order)
        .all()
    )

    return QuestionResponse(
        id=str(question.id),
        question_text=question.question_text,
        question_type=question.question_type,
        topic=question.topic,
        difficulty=question.difficulty,
        explanation=question.explanation,
        marks=question.marks,
        negative_marks=question.negative_marks,
        created_by=str(question.created_by),
        status=question.status,
        options=[
            QuestionOptionResponse(
                id=str(option.id),
                option_text=option.option_text,
                is_correct=option.is_correct,
                option_order=option.option_order,
            )
            for option in options
        ],
        created_at=question.created_at,
        updated_at=question.updated_at,
    )
    
@router.get(
    "",
    response_model=list[QuestionResponse]
)
def list_questions(
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    status: str | None = None,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    query = db.query(Question)

    if topic:
        query = query.filter(Question.topic == topic)

    if difficulty:
        query = query.filter(Question.difficulty == difficulty)

    if question_type:
        query = query.filter(Question.question_type == question_type)

    if status:
        query = query.filter(Question.status == status)

    questions = (
        query
        .order_by(Question.created_at.desc())
        .all()
    )

    response = []

    for question in questions:
        options = (
            db.query(QuestionOption)
            .filter(
                QuestionOption.question_id == question.id
            )
            .order_by(QuestionOption.option_order)
            .all()
        )

        response.append(
            QuestionResponse(
                id=str(question.id),
                question_text=question.question_text,
                question_type=question.question_type,
                topic=question.topic,
                difficulty=question.difficulty,
                explanation=question.explanation,
                marks=question.marks,
                negative_marks=question.negative_marks,
                created_by=str(question.created_by),
                status=question.status,
                options=[
                    QuestionOptionResponse(
                        id=str(option.id),
                        option_text=option.option_text,
                        is_correct=option.is_correct,
                        option_order=option.option_order,
                    )
                    for option in options
                ],
                created_at=question.created_at,
                updated_at=question.updated_at,
            )
        )

    return response

@router.post(
    "/import",
    response_model=QuestionPasteImportResponse
)
def import_questions(
    request: QuestionPasteImportRequest,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    parsed_questions = parse_questions(request.text)

    if not parsed_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid questions found in the provided text"
        )

    created_questions = []

    try:
        for parsed in parsed_questions:

            question = Question(
                question_text=parsed.question_text,
                question_type="MCQ",
                topic=parsed.topic,
                difficulty=parsed.difficulty,
                explanation=None,
                marks=parsed.marks,
                negative_marks=parsed.negative_marks,
                created_by=current_user.id,
                status="DRAFT",
            )

            db.add(question)
            db.flush()

            for option in parsed.options:

                is_correct = (
                    option.option_order
                    in parsed.correct_answers
                )

                db.add(
                    QuestionOption(
                        question_id=question.id,
                        option_text=option.option_text,
                        is_correct=is_correct,
                        option_order=option.option_order,
                    )
                )

            created_questions.append(question)

        db.commit()

        for question in created_questions:
            db.refresh(question)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Question import failed. No questions were imported."
        )

    return QuestionPasteImportResponse(
    questions=[
        ImportedQuestionResponse(
            id=str(question.id),
            status=question.status,
            question_text=parsed.question_text,
            options=parsed.options,
            correct_answers=parsed.correct_answers,
            topic=parsed.topic,
            difficulty=parsed.difficulty,
            marks=parsed.marks,
            negative_marks=parsed.negative_marks,
        )
        for question, parsed in zip(
            created_questions,
            parsed_questions
        )
    ],
    total_questions=len(created_questions),
)

@router.get(
    "/{question_id}",
    response_model=QuestionResponse
)
def get_question(
    question_id: str,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    options = (
        db.query(QuestionOption)
        .filter(
            QuestionOption.question_id == question.id
        )
        .order_by(QuestionOption.option_order)
        .all()
    )

    return QuestionResponse(
        id=str(question.id),
        question_text=question.question_text,
        question_type=question.question_type,
        topic=question.topic,
        difficulty=question.difficulty,
        explanation=question.explanation,
        marks=question.marks,
        negative_marks=question.negative_marks,
        created_by=str(question.created_by),
        status=question.status,
        options=[
            QuestionOptionResponse(
                id=str(option.id),
                option_text=option.option_text,
                is_correct=option.is_correct,
                option_order=option.option_order,
            )
            for option in options
        ],
        created_at=question.created_at,
        updated_at=question.updated_at,
    )
    
@router.patch(
    "/{question_id}",
    response_model=QuestionResponse
)
def update_question(
    question_id: str,
    request: QuestionUpdateRequest,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.status not in {"DRAFT", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft or rejected questions can be updated"
        )

    if current_user.role == "EXAMINER" and question.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own questions")

    if request.question_text is not None:
        question.question_text = request.question_text

    if request.topic is not None:
        question.topic = request.topic

    if request.difficulty is not None:
        question.difficulty = request.difficulty

    if request.explanation is not None:
        question.explanation = request.explanation

    if request.marks is not None:
        question.marks = request.marks

    if request.negative_marks is not None:
        question.negative_marks = request.negative_marks

    if request.options is not None:

        if question.question_type == "MCQ":
            if len(request.options) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MCQ must have at least 2 options"
                )

            correct_count = sum(
                option.is_correct
                for option in request.options
            )

            if correct_count != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MCQ must have exactly one correct option"
                )

        elif question.question_type == "MULTIPLE_SELECT":
            if len(request.options) < 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MULTIPLE_SELECT must have at least 2 options"
                )

            correct_count = sum(
                option.is_correct
                for option in request.options
            )

            if correct_count < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "MULTIPLE_SELECT must have at least "
                        "one correct option"
                    )
                )

        elif question.question_type == "TRUE_FALSE":
            if len(request.options) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="TRUE_FALSE must have exactly 2 options"
                )

            correct_count = sum(
                option.is_correct
                for option in request.options
            )

            if correct_count != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "TRUE_FALSE must have exactly "
                        "one correct option"
                    )
                )

        elif question.question_type == "SHORT_ANSWER":
            if request.options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SHORT_ANSWER cannot have options"
                )

        db.query(QuestionOption).filter(
            QuestionOption.question_id == question.id
        ).delete(
            synchronize_session=False
        )

        for option in request.options:
            db.add(
                QuestionOption(
                    question_id=question.id,
                    option_text=option.option_text,
                    is_correct=option.is_correct,
                    option_order=option.option_order,
                )
            )
    if question.status == "REJECTED":
        question.status = "DRAFT"        

    db.commit()
    db.refresh(question)

    options = (
        db.query(QuestionOption)
        .filter(
            QuestionOption.question_id == question.id
        )
        .order_by(QuestionOption.option_order)
        .all()
    )

    return QuestionResponse(
        id=str(question.id),
        question_text=question.question_text,
        question_type=question.question_type,
        topic=question.topic,
        difficulty=question.difficulty,
        explanation=question.explanation,
        marks=question.marks,
        negative_marks=question.negative_marks,
        created_by=str(question.created_by),
        status=question.status,
        options=[
            QuestionOptionResponse(
                id=str(option.id),
                option_text=option.option_text,
                is_correct=option.is_correct,
                option_order=option.option_order,
            )
            for option in options
        ],
        created_at=question.created_at,
        updated_at=question.updated_at,
    )

@router.post(
    "/{question_id}/approve",
    response_model=QuestionResponse
)
def approve_question(
    question_id: str,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft questions can be approved"
        )

    if current_user.role == "EXAMINER" and question.created_by == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An examiner cannot approve their own question")

    question.status = "APPROVED"

    db.commit()
    db.refresh(question)

    options = (
        db.query(QuestionOption)
        .filter(
            QuestionOption.question_id == question.id
        )
        .order_by(QuestionOption.option_order)
        .all()
    )

    return QuestionResponse(
        id=str(question.id),
        question_text=question.question_text,
        question_type=question.question_type,
        topic=question.topic,
        difficulty=question.difficulty,
        explanation=question.explanation,
        marks=question.marks,
        negative_marks=question.negative_marks,
        created_by=str(question.created_by),
        status=question.status,
        options=[
            QuestionOptionResponse(
                id=str(option.id),
                option_text=option.option_text,
                is_correct=option.is_correct,
                option_order=option.option_order,
            )
            for option in options
        ],
        created_at=question.created_at,
        updated_at=question.updated_at,
    )
    
@router.post(
    "/{question_id}/reject",
    response_model=QuestionResponse
)
def reject_question(
    question_id: str,
    request: QuestionRejectRequest,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    if question.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft questions can be rejected"
        )

    if current_user.role == "EXAMINER" and question.created_by == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An examiner cannot reject their own question")

    question.status = "REJECTED"

    review = QuestionReview(
        question_id=question.id,
        reviewer_id=current_user.id,
        action="REJECTED",
        reason=request.reason,
    )

    db.add(review)

    db.commit()
    db.refresh(question)

    options = (
        db.query(QuestionOption)
        .filter(
            QuestionOption.question_id == question.id
        )
        .order_by(QuestionOption.option_order)
        .all()
    )

    return QuestionResponse(
        id=str(question.id),
        question_text=question.question_text,
        question_type=question.question_type,
        topic=question.topic,
        difficulty=question.difficulty,
        explanation=question.explanation,
        marks=question.marks,
        negative_marks=question.negative_marks,
        created_by=str(question.created_by),
        status=question.status,
        options=[
            QuestionOptionResponse(
                id=str(option.id),
                option_text=option.option_text,
                is_correct=option.is_correct,
                option_order=option.option_order,
            )
            for option in options
        ],
        created_at=question.created_at,
        updated_at=question.updated_at,
    )
    
@router.get(
    "/{question_id}/reviews",
    response_model=list[QuestionReviewResponse]
)
def get_question_reviews(
    question_id: str,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db)
):
    question = (
        db.query(Question)
        .filter(Question.id == question_id)
        .first()
    )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    reviews = (
        db.query(QuestionReview)
        .filter(
            QuestionReview.question_id == question.id
        )
        .order_by(QuestionReview.reviewed_at.asc())
        .all()
    )

    return [
        QuestionReviewResponse(
            id=str(review.id),
            question_id=str(review.question_id),
            reviewer_id=str(review.reviewer_id),
            action=review.action,
            reason=review.reason,
            reviewed_at=review.reviewed_at,
        )
        for review in reviews
    ]
    
@router.post(
    "/import/preview",
    response_model=QuestionPasteImportResponse
)
def preview_question_import(
    request: QuestionPasteImportRequest,
    current_user: User = Depends(require_admin_or_examiner),
):
    questions = parse_questions(request.text)

    return QuestionPasteImportResponse(
        questions=[
            ImportedQuestionResponse(
                id="",
                status="PREVIEW",
                question_text=question.question_text,
                options=question.options,
                correct_answers=question.correct_answers,
                topic=question.topic,
                difficulty=question.difficulty,
                marks=question.marks,
                negative_marks=question.negative_marks,
            )
            for question in questions
        ],
        total_questions=len(questions),
    )
