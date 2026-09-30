from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.models.user import User


def require_role(*allowed_roles: str):

    def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )

        return current_user

    return role_checker


def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


def require_examiner(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role != "EXAMINER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Examiner access required"
        )

    return current_user


def require_student(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required"
        )

    return current_user


def require_admin_or_examiner(
    current_user: User = Depends(get_current_user)
) -> User:

    if current_user.role not in {"ADMIN", "EXAMINER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or examiner access required"
        )

    return current_user