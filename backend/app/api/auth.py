from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    record_audit_log,
    require_role,
    verify_password,
)
from app.models.models import User
from app.schemas.schemas import LoginRequest, LoginResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your platform administrator.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    record_audit_log(
        db=db,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        details={"role": user.role},
        actor=user,
        request=request,
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    users = list(db.scalars(select(User).order_by(User.id.asc())).all())
    return [UserOut.model_validate(u) for u in users]
