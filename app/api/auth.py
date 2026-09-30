from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest,LoginRequest, TokenResponse
from app.core.security import hash_password

from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)

from app.dependencies.roles import (
    require_admin,
    require_examiner,
    require_student
)

from app.dependencies.auth import get_current_user

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    # Check whether the email already exists
    existing_user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered"
        )

    # Hash the password before storing it
    hashed_password = hash_password(request.password)

    # Create the user
    user = User(
        full_name=request.full_name,
        email=request.email,
        password_hash=hashed_password,
        role="STUDENT",
        student_id=request.student_id,
        phone=request.phone
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User registered successfully",
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role
        }
    }
@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(
        request.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }   
    

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": str(current_user.id),
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "student_id": current_user.student_id,
        "phone": current_user.phone,
        "status": current_user.status
    }
    

    
@router.get("/test/admin")
def test_admin_access(
    current_user: User = Depends(require_admin)
):
    return {
        "message": "Admin access granted",
        "user": current_user.email
    }


@router.get("/test/examiner")
def test_examiner_access(
    current_user: User = Depends(require_examiner)
):
    return {
        "message": "Examiner access granted",
        "user": current_user.email
    }


@router.get("/test/student")
def test_student_access(
    current_user: User = Depends(require_student)
):
    return {
        "message": "Student access granted",
        "user": current_user.email
    }