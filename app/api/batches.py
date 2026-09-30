from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.batch import Batch
from app.models.user import User
from app.schemas.batch import BatchCreateRequest, BatchResponse, BatchJoinRequest, BatchMemberResponse
from app.dependencies.roles import require_admin, require_student
from app.models.batch_member import BatchMember


router = APIRouter(
    prefix="/api/batches",
    tags=["Batches"]
)


@router.post(
    "",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED
)
def create_batch(
    request: BatchCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    existing_batch = (
        db.query(Batch)
        .filter(Batch.code == request.code)
        .first()
    )

    if existing_batch:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch code already exists"
        )

    batch = Batch(
        name=request.name,
        code=request.code,
        description=request.description,
        created_by=current_user.id,
        status="ACTIVE"
    )

    db.add(batch)
    db.commit()
    db.refresh(batch)

    return BatchResponse(
        id=str(batch.id),
        name=batch.name,
        code=batch.code,
        description=batch.description,
        status=batch.status,
        created_by=str(batch.created_by)
    )
    
@router.post(
    "/join",
    response_model=BatchMemberResponse,
    status_code=status.HTTP_201_CREATED
)
def join_batch(
    request: BatchJoinRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    batch = (
        db.query(Batch)
        .filter(Batch.code == request.code)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    if batch.status != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="This batch is not active"
        )

    existing_membership = (
        db.query(BatchMember)
        .filter(
            BatchMember.batch_id == batch.id,
            BatchMember.student_id == current_user.id
        )
        .first()
    )

    if existing_membership:
        raise HTTPException(
            status_code=409,
            detail="You are already a member of this batch"
        )

    membership = BatchMember(
        batch_id=batch.id,
        student_id=current_user.id,
        status="ACTIVE"
    )

    db.add(membership)
    db.commit()
    db.refresh(membership)

    return BatchMemberResponse(
        id=str(membership.id),
        batch_id=str(membership.batch_id),
        student_id=str(membership.student_id),
        status=membership.status
    )
    
@router.get("", response_model=list[BatchResponse])
def get_batches(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batches = (
        db.query(Batch)
        .order_by(Batch.created_at.desc())
        .all()
    )

    return [
        BatchResponse(
            id=str(batch.id),
            name=batch.name,
            code=batch.code,
            description=batch.description,
            status=batch.status,
            created_by=str(batch.created_by)
        )
        for batch in batches
    ]
    
@router.get("/my", response_model=list[BatchResponse])
def get_my_batches(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    batches = (
        db.query(Batch)
        .join(
            BatchMember,
            BatchMember.batch_id == Batch.id
        )
        .filter(
            BatchMember.student_id == current_user.id,
            BatchMember.status == "ACTIVE",
            Batch.status == "ACTIVE"
        )
        .order_by(Batch.created_at.desc())
        .all()
    )

    return [
        BatchResponse(
            id=str(batch.id),
            name=batch.name,
            code=batch.code,
            description=batch.description,
            status=batch.status,
            created_by=str(batch.created_by)
        )
        for batch in batches
    ]

@router.get("/{batch_code}", response_model=BatchResponse)
def get_batch(
    batch_code: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = (
        db.query(Batch)
        .filter(Batch.code == batch_code)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    return BatchResponse(
        id=str(batch.id),
        name=batch.name,
        code=batch.code,
        description=batch.description,
        status=batch.status,
        created_by=str(batch.created_by)
    )
    

@router.get("/{batch_code}/members")
def get_batch_members(
    batch_code: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = (
        db.query(Batch)
        .filter(Batch.code == batch_code)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    members = (
        db.query(BatchMember, User)
        .join(User, BatchMember.student_id == User.id)
        .filter(BatchMember.batch_id == batch.id)
        .order_by(BatchMember.joined_at.desc())
        .all()
    )

    return [
        {
            "id": str(member.id),
            "student_id": str(student.id),
            "full_name": student.full_name,
            "email": student.email,
            "student_code": student.student_id,
            "phone": student.phone,
            "status": member.status,
            "joined_at": member.joined_at
        }
        for member, student in members
    ]

@router.delete("/{batch_code}/members/{student_id}")
def remove_batch_member(
    batch_code: str,
    student_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    batch = (
        db.query(Batch)
        .filter(Batch.code == batch_code)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found"
        )

    membership = (
        db.query(BatchMember)
        .join(User, BatchMember.student_id == User.id)
        .filter(
            BatchMember.batch_id == batch.id,
            User.id == student_id
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=404,
            detail="Student is not a member of this batch"
        )

    db.delete(membership)
    db.commit()

    return {
        "message": "Student removed from batch successfully"
    }