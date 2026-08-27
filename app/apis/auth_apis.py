from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.databases import async_get_db
from app.models.user import User
from app.repositories.user_repository import create_user, get_user_by_email
from app.schemas.user import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1")


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(async_get_db)):
    existing_user = await get_user_by_email(db, payload.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 이메일입니다.")

    user = await create_user(
        db,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        department=payload.department,
        gender=payload.gender,
        phone_number=payload.phone_number,
        role="PENDING",
    )
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(async_get_db)):
    user = await get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 일치하지 않습니다.")

    access_token = create_access_token(user.uuid)
    refresh_token = create_refresh_token(user.uuid)
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(async_get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token이 없습니다. 재로그인이 필요합니다.")

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token이 아닙니다.")

    from uuid import UUID

    from app.repositories.user_repository import get_user_by_id

    user = await get_user_by_id(db, UUID(payload["user_id"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")

    new_access_token = create_access_token(user.uuid)
    new_refresh_token = create_refresh_token(user.uuid)
    set_refresh_cookie(response, new_refresh_token)
    return TokenResponse(access_token=new_access_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    response.delete_cookie("refresh_token")
    return None


@router.get("/users/me", response_model=UserResponse)
async def get_my_info(current_user: User = Depends(get_current_user)):
    return current_user