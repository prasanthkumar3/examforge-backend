from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.user import User


def ensure_exam_access(exam: Exam, current_user: User) -> None:
    if current_user.role == "ADMIN":
        return
    if current_user.role == "EXAMINER" and exam.created_by == current_user.id:
        return
    raise HTTPException(status_code=403, detail="You do not have access to this exam")


def get_exam_or_404(db: Session, exam_id: str, current_user: User | None = None) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if current_user is not None:
        ensure_exam_access(exam, current_user)
    return exam
