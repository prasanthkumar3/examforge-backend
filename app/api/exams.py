from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from datetime import datetime, timezone



from app.database import get_db

from app.models.exam import Exam

from app.models.batch_member import BatchMember

from app.models.exam_batch import ExamBatch

from app.models.batch import Batch

from app.models.user import User

from app.schemas.exam import (

    ExamCreateRequest,

    ExamResponse,

    ExamUpdateRequest, 

    ExamQuestionCreateRequest,

    ExamQuestionOrderItem,

    ExamQuestionReorderRequest,

    ExamQuestionUpdateRequest

)

from app.dependencies.roles import require_admin_or_examiner,require_student

from app.models.exam_question import ExamQuestion

from app.models.question import Question



from app.models.question_option import QuestionOption
from app.services.access import ensure_exam_access
from app.schemas.question_import import (
    QuestionPasteImportRequest,
    QuestionPasteImportResponse,
    ImportedQuestionResponse,
)
from app.services.question_parser import parse_questions

 

 

router = APIRouter(

    prefix="/api/exams",

    tags=["Examinations"]

)

 

 

@router.post("/", response_model=ExamResponse)

def create_exam(

    request: ExamCreateRequest,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    # -----------------------------------------------------

    # Validate room code uniqueness

    # -----------------------------------------------------

 

    if request.room_code:

        existing_exam = (

            db.query(Exam)

            .filter(Exam.room_code == request.room_code.strip())

            .first()

        )

 

        if existing_exam:

            raise HTTPException(

                status_code=status.HTTP_409_CONFLICT,

                detail="Exam room code already exists"

            )

 

    # -----------------------------------------------------

    # Create exam

    # -----------------------------------------------------

 

    exam = Exam(

        title=request.title.strip(),

        description=request.description,

        instructions=request.instructions,

        exam_type=request.exam_type,

        room_code=(

            request.room_code.strip()

            if request.room_code

            else None

        ),

        duration_minutes=request.duration_minutes,

        start_at=request.start_at,

        end_at=request.end_at,

        max_attempts=request.max_attempts,

        completion_target=request.completion_target,

        auto_close_on_target=request.auto_close_on_target,

        created_by=current_user.id,

        status="DRAFT"

    )

 

    db.add(exam)

    db.flush()

 

    # -----------------------------------------------------

    # Assign batches

    #

    # This works for:

    # BATCH

    # BOTH

    # -----------------------------------------------------

 

    if request.exam_type in {"BATCH", "BOTH"}:

 

        batches = (

            db.query(Batch)

            .filter(

                Batch.code.in_(request.batch_codes)

            )

            .all()

        )

 

        found_codes = {

            batch.code

            for batch in batches

        }

 

        requested_codes = set(request.batch_codes)

 

        missing_codes = requested_codes - found_codes

 

        if missing_codes:

            db.rollback()

 

            raise HTTPException(

                status_code=400,

                detail=(

                    "Batch not found: "

                    + ", ".join(sorted(missing_codes))

                )

            )

 

        for batch in batches:

 

            exam_batch = ExamBatch(

                exam_id=exam.id,

                batch_id=batch.id

            )

 

            db.add(exam_batch)

 

    # -----------------------------------------------------

    # Save

    # -----------------------------------------------------

 

    db.commit()

    db.refresh(exam)

 

    return ExamResponse(

        id=str(exam.id),

        title=exam.title,

        description=exam.description,

        instructions=exam.instructions,

        exam_type=exam.exam_type,

        room_code=exam.room_code,

        duration_minutes=exam.duration_minutes,

        start_at=exam.start_at,

        end_at=exam.end_at,

        max_attempts=exam.max_attempts,

        completion_target=exam.completion_target,

        auto_close_on_target=exam.auto_close_on_target,

        created_by=str(exam.created_by),

        status=exam.status,

        created_at=exam.created_at,

        updated_at=exam.updated_at

    )

 

@router.get("", response_model=list[ExamResponse])

def get_exams(

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    query = db.query(Exam)
    if current_user.role == "EXAMINER":
        query = query.filter(Exam.created_by == current_user.id)
    exams = query.order_by(Exam.created_at.desc()).all()

 

    return [

        ExamResponse(

            id=str(exam.id),

            title=exam.title,

            description=exam.description,

            instructions=exam.instructions,

            exam_type=exam.exam_type,

            room_code=exam.room_code,

            duration_minutes=exam.duration_minutes,

            start_at=exam.start_at,

            end_at=exam.end_at,

            max_attempts=exam.max_attempts,

            completion_target=exam.completion_target,

            auto_close_on_target=exam.auto_close_on_target,

            created_by=str(exam.created_by),

            status=exam.status,

            created_at=exam.created_at,

            updated_at=exam.updated_at

        )

        for exam in exams

    ]

 

@router.patch("/{exam_id}", response_model=ExamResponse)

def update_exam(

    exam_id: str,

    request: ExamUpdateRequest,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=404,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

    if exam.status != "DRAFT":

        raise HTTPException(

            status_code=400,

            detail="Only draft exams can be edited"

        )

 

    updates = request.model_dump(exclude_unset=True)
    requested_type = updates.get("exam_type", exam.exam_type)
    requested_room = updates.get("room_code", exam.room_code)
    requested_batches = updates.pop("batch_codes", None)

    if requested_type not in {"COMMON", "BATCH", "BOTH"}:
        raise HTTPException(status_code=400, detail="Invalid exam_type")
    if requested_type in {"COMMON", "BOTH"} and not requested_room:
        raise HTTPException(status_code=400, detail="room_code is required for COMMON or BOTH exams")
    if requested_type == "BATCH" and requested_room:
        raise HTTPException(status_code=400, detail="BATCH exams cannot have a room_code")

    if requested_room:
        existing = db.query(Exam).filter(Exam.room_code == requested_room.strip(), Exam.id != exam.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Exam room code already exists")
        updates["room_code"] = requested_room.strip()
    else:
        updates["room_code"] = None

    for field, value in updates.items():
        setattr(exam, field, value)

    if exam.start_at and exam.end_at and exam.end_at <= exam.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")
    if exam.auto_close_on_target and exam.completion_target is None:
        raise HTTPException(status_code=400, detail="completion_target is required when auto_close_on_target is enabled")

    if requested_batches is not None:
        if exam.exam_type in {"BATCH", "BOTH"} and not requested_batches:
            raise HTTPException(status_code=400, detail="At least one batch is required for BATCH or BOTH exams")
        db.query(ExamBatch).filter(ExamBatch.exam_id == exam.id).delete(synchronize_session=False)
        if exam.exam_type in {"BATCH", "BOTH"}:
            batches = db.query(Batch).filter(Batch.code.in_(requested_batches)).all()
            found = {batch.code for batch in batches}
            missing = set(requested_batches) - found
            if missing:
                db.rollback()
                raise HTTPException(status_code=400, detail="Batch not found: " + ", ".join(sorted(missing)))
            for batch in batches:
                db.add(ExamBatch(exam_id=exam.id, batch_id=batch.id))
    elif "exam_type" in updates:
        if exam.exam_type == "COMMON":
            db.query(ExamBatch).filter(ExamBatch.exam_id == exam.id).delete(synchronize_session=False)
        elif exam.exam_type in {"BATCH", "BOTH"}:
            has_batch = db.query(ExamBatch).filter(ExamBatch.exam_id == exam.id).first() is not None
            if not has_batch:
                raise HTTPException(status_code=400, detail="At least one batch is required for BATCH or BOTH exams")

    db.commit()

    db.refresh(exam)

 

    return ExamResponse(

        id=str(exam.id),

        title=exam.title,

        description=exam.description,

        instructions=exam.instructions,

        exam_type=exam.exam_type,

        room_code=exam.room_code,

        duration_minutes=exam.duration_minutes,

        start_at=exam.start_at,

        end_at=exam.end_at,

        max_attempts=exam.max_attempts,

        completion_target=exam.completion_target,

        auto_close_on_target=exam.auto_close_on_target,

        created_by=str(exam.created_by),

        status=exam.status,

        created_at=exam.created_at,

        updated_at=exam.updated_at

    )

    

@router.post("/{exam_id}/publish", response_model=ExamResponse)
def publish_exam(
    exam_id: str,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    ensure_exam_access(exam, current_user)

    if exam.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail="Only draft exams can be published"
        )

    # An exam must contain at least one question before publishing.
    question_count = (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam.id)
        .count()
    )

    if question_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot publish an exam without questions"
        )

    exam.status = "PUBLISHED"

    db.commit()
    db.refresh(exam)

    return ExamResponse(
        id=str(exam.id),
        title=exam.title,
        description=exam.description,
        instructions=exam.instructions,
        exam_type=exam.exam_type,
        room_code=exam.room_code,
        duration_minutes=exam.duration_minutes,
        start_at=exam.start_at,
        end_at=exam.end_at,
        max_attempts=exam.max_attempts,
        completion_target=exam.completion_target,
        auto_close_on_target=exam.auto_close_on_target,
        created_by=str(exam.created_by),
        status=exam.status,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )

@router.post("/{exam_id}/close", response_model=ExamResponse)

def close_exam(

    exam_id: str,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=404,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

    if exam.status != "PUBLISHED":

        raise HTTPException(

            status_code=400,

            detail="Only published exams can be closed"

        )

 

    exam.status = "CLOSED"

 

    db.commit()

    db.refresh(exam)

 

    return ExamResponse(

        id=str(exam.id),

        title=exam.title,

        description=exam.description,

        instructions=exam.instructions,

        exam_type=exam.exam_type,

        room_code=exam.room_code,

        duration_minutes=exam.duration_minutes,

        start_at=exam.start_at,

        end_at=exam.end_at,

        max_attempts=exam.max_attempts,

        completion_target=exam.completion_target,

        auto_close_on_target=exam.auto_close_on_target,

        created_by=str(exam.created_by),

        status=exam.status,

        created_at=exam.created_at,

        updated_at=exam.updated_at

    )

@router.post("/{exam_id}/reopen", response_model=ExamResponse)
def reopen_exam(
    exam_id: str,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    ensure_exam_access(exam, current_user)

    if exam.status != "CLOSED":
        raise HTTPException(
            status_code=400,
            detail="Only closed exams can be reopened"
        )

    # Reopening returns the exam to DRAFT.
    # Questions can then be added/removed/reordered safely.
    exam.status = "DRAFT"

    db.commit()
    db.refresh(exam)

    return ExamResponse(
        id=str(exam.id),
        title=exam.title,
        description=exam.description,
        instructions=exam.instructions,
        exam_type=exam.exam_type,
        room_code=exam.room_code,
        duration_minutes=exam.duration_minutes,
        start_at=exam.start_at,
        end_at=exam.end_at,
        max_attempts=exam.max_attempts,
        completion_target=exam.completion_target,
        auto_close_on_target=exam.auto_close_on_target,
        created_by=str(exam.created_by),
        status=exam.status,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )

@router.post("/{exam_id}/questions")

def add_question_to_exam(

    exam_id: str,

    request: ExamQuestionCreateRequest,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

    if exam.status != "DRAFT":

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Questions can only be added to a draft exam"

        )

 

    question = (

        db.query(Question)

        .filter(Question.id == request.question_id)

        .first()

    )

 

    if not question:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Question not found"

        )

 

    if question.status != "APPROVED":

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Only approved questions can be added to an exam"

        )

 

    existing = (

        db.query(ExamQuestion)

        .filter(

            ExamQuestion.exam_id == exam.id,

            ExamQuestion.question_id == question.id

        )

        .first()

    )

 

    if existing:

        raise HTTPException(

            status_code=status.HTTP_409_CONFLICT,

            detail="Question is already added to this exam"

        )

 

    existing_order = (

        db.query(ExamQuestion)

        .filter(

            ExamQuestion.exam_id == exam.id,

            ExamQuestion.question_order == request.question_order

        )

        .first()

    )

 

    if existing_order:

        raise HTTPException(

            status_code=status.HTTP_409_CONFLICT,

            detail="Question order is already used in this exam"

        )

 

    exam_question = ExamQuestion(

        exam_id=exam.id,

        question_id=question.id,

        question_order=request.question_order,

        marks=request.marks,

        negative_marks=request.negative_marks,

    )

 

    db.add(exam_question)

    db.commit()

    db.refresh(exam_question)

 

    return {

        "id": str(exam_question.id),

        "exam_id": str(exam_question.exam_id),

        "question_id": str(exam_question.question_id),

        "question_order": exam_question.question_order,

        "marks": exam_question.marks,

        "negative_marks": exam_question.negative_marks,

    }

    

@router.post(
    "/{exam_id}/questions/import/preview",
    response_model=QuestionPasteImportResponse,
)
def preview_exam_question_import(
    exam_id: str,
    request: QuestionPasteImportRequest,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    ensure_exam_access(exam, current_user)

    if exam.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Questions can only be imported into a draft exam",
        )

    parsed_questions = parse_questions(request.text)

    if not parsed_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid questions found in the provided text",
        )

    return QuestionPasteImportResponse(
        questions=[
            ImportedQuestionResponse(
                id="",
                status="PREVIEW",
                question_text=parsed.question_text,
                options=parsed.options,
                correct_answers=parsed.correct_answers,
                topic=parsed.topic,
                difficulty=parsed.difficulty,
                marks=parsed.marks,
                negative_marks=parsed.negative_marks,
            )
            for parsed in parsed_questions
        ],
        total_questions=len(parsed_questions),
    )


@router.post(
    "/{exam_id}/questions/import",
    response_model=QuestionPasteImportResponse,
)
def import_questions_into_exam(
    exam_id: str,
    request: QuestionPasteImportRequest,
    current_user: User = Depends(require_admin_or_examiner),
    db: Session = Depends(get_db),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    ensure_exam_access(exam, current_user)

    if exam.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Questions can only be imported into a draft exam",
        )

    parsed_questions = parse_questions(request.text)

    if not parsed_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid questions found in the provided text",
        )

    current_max_order = (
        db.query(func.max(ExamQuestion.question_order))
        .filter(ExamQuestion.exam_id == exam.id)
        .scalar()
    )
    next_order = (current_max_order or 0) + 1

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
                db.add(
                    QuestionOption(
                        question_id=question.id,
                        option_text=option.option_text,
                        is_correct=option.option_order in parsed.correct_answers,
                        option_order=option.option_order,
                    )
                )

            exam_question = ExamQuestion(
                exam_id=exam.id,
                question_id=question.id,
                question_order=next_order,
                marks=parsed.marks,
                negative_marks=parsed.negative_marks,
            )

            db.add(exam_question)
            created_questions.append(question)
            next_order += 1

        db.commit()

        for question in created_questions:
            db.refresh(question)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Question import failed. No questions were added to the exam.",
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
                parsed_questions,
            )
        ],
        total_questions=len(created_questions),
    )


@router.get("/{exam_id}/questions")

def get_exam_questions(

    exam_id: str,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

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

 

    options_by_question = {}

 

    for option in options:

        options_by_question.setdefault(

            option.question_id,

            []

        ).append(option)

 

    questions = []

 

    for exam_question, question in rows:

        questions.append({

            "id": str(exam_question.id),

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

 

    return {

        "exam": {

            "id": str(exam.id),

            "room_code": exam.room_code,

            "title": exam.title,

        },

        "total_questions": len(questions),

        "questions": questions,

    }

    

@router.delete("/{exam_id}/questions/{question_id}")

def remove_question_from_exam(

    exam_id: str,

    question_id: str,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

    if exam.status != "DRAFT":

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Questions can only be removed from a draft exam"

        )

 

    exam_question = (

        db.query(ExamQuestion)

        .filter(

            ExamQuestion.exam_id == exam.id,

            ExamQuestion.question_id == question_id

        )

        .first()

    )

 

    if not exam_question:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Question is not assigned to this exam"

        )

 

    db.delete(exam_question)

    db.commit()

 

    return {

        "message": "Question removed from exam successfully"

    }

 

@router.put("/{exam_id}/questions/reorder")

def reorder_exam_questions(

    exam_id: str,

    request: ExamQuestionReorderRequest,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

    if exam.status != "DRAFT":

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Questions can only be reordered in a draft exam"

        )

 

    if not request.questions:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Question list cannot be empty"

        )

 

    requested_ids = [

        item.question_id

        for item in request.questions

    ]

 

    requested_orders = [

        item.question_order

        for item in request.questions

    ]

 

    # No duplicate question IDs

    if len(requested_ids) != len(set(requested_ids)):

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Duplicate question IDs are not allowed"

        )

 

    # No duplicate question orders

    if len(requested_orders) != len(set(requested_orders)):

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Duplicate question orders are not allowed"

        )

 

    # Orders must be continuous: 1, 2, 3, ...

    expected_orders = set(

        range(1, len(request.questions) + 1)

    )

 

    if set(requested_orders) != expected_orders:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Question orders must start at 1 and be continuous"

        )

 

    exam_questions = (

        db.query(ExamQuestion)

        .filter(

            ExamQuestion.exam_id == exam.id

        )

        .all()

    )

 

    existing_ids = {

        str(item.question_id)

        for item in exam_questions

    }

 

    requested_id_set = set(requested_ids)

 

    # The request must contain every question

    # currently assigned to the exam.

    if existing_ids != requested_id_set:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=(

                "Reorder request must contain exactly "

                "all questions currently assigned to the exam"

            )

        )

 

    try:

        # Move existing orders temporarily outside

        # the valid range so the unique constraint

        # cannot collide during the swap.

        for index, item in enumerate(exam_questions, start=1):

            item.question_order = -(index)

 

        db.flush()

 

        order_map = {

            item.question_id: item.question_order

            for item in request.questions

        }

 

        for item in exam_questions:

            item.question_order = order_map[

                str(item.question_id)

            ]

 

        db.commit()

 

    except Exception:

        db.rollback()

 

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Failed to reorder exam questions"

        )

 

    return {

        "message": "Exam questions reordered successfully"

    }

 

@router.patch("/{exam_id}/questions/{question_id}")

def update_exam_question_scoring(

    exam_id: str,

    question_id: str,

    request: ExamQuestionUpdateRequest,

    current_user: User = Depends(require_admin_or_examiner),

    db: Session = Depends(get_db)

):

    exam = (

        db.query(Exam)

        .filter(Exam.id == exam_id)

        .first()

    )

 

    if not exam:

        raise HTTPException(

            status_code=404,

            detail="Exam not found"

        )

    ensure_exam_access(exam, current_user)

 

    if exam.status != "DRAFT":

        raise HTTPException(

            status_code=400,

            detail="Question scoring can only be changed in a draft exam"

        )

 

    exam_question = (

        db.query(ExamQuestion)

        .filter(

            ExamQuestion.exam_id == exam.id,

            ExamQuestion.question_id == question_id

        )

        .first()

    )

 

    if not exam_question:

        raise HTTPException(

            status_code=404,

            detail="Question is not assigned to this exam"

        )

 

    exam_question.marks = request.marks

    exam_question.negative_marks = request.negative_marks

 

    db.commit()

    db.refresh(exam_question)

 

    return {

        "id": str(exam_question.id),

        "exam_id": str(exam_question.exam_id),

        "question_id": str(exam_question.question_id),

        "question_order": exam_question.question_order,

        "marks": exam_question.marks,

        "negative_marks": exam_question.negative_marks,

    }
    


@router.get("/student/available")
def get_student_available_exams(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    exams = (
        db.query(Exam)
        .join(
            ExamBatch,
            ExamBatch.exam_id == Exam.id,
        )
        .join(
            BatchMember,
            BatchMember.batch_id == ExamBatch.batch_id,
        )
        .filter(
            BatchMember.student_id == current_user.id,
            BatchMember.status == "ACTIVE",
            Exam.status == "PUBLISHED",
            Exam.exam_type.in_(["BATCH", "BOTH"]),
            or_(
                Exam.start_at.is_(None),
                Exam.start_at <= now,
            ),
            or_(
                Exam.end_at.is_(None),
                Exam.end_at >= now,
            ),
        )
        .order_by(
            Exam.start_at.asc().nulls_last(),
            Exam.created_at.desc(),
        )
        .distinct()
        .all()
    )

    return [
        {
            "id": str(exam.id),
            "title": exam.title,
            "description": exam.description,
            "instructions": exam.instructions,
            "exam_type": exam.exam_type,
            "duration_minutes": exam.duration_minutes,
            "start_at": exam.start_at,
            "end_at": exam.end_at,
            "max_attempts": exam.max_attempts,
            "status": exam.status,
        }
        for exam in exams
    ]