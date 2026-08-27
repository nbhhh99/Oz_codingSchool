import math
import uuid as uuid_pkg

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.models.user import DepartmentEnum, User
from app.repositories.user_repository import (
    get_user_by_id,
    get_users,
)
from app.schemas.user import (
    PasswordChangeRequest,
    UserListResponse,
    UserResponse,
    UserRoleResponse,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)
from app.services.auth_service import get_current_user
from app.services.user_service import (
    change_my_info,
    change_my_password,
    change_user_role,
    get_current_admin,
    withdraw_user,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["User Management"],
)


@router.get(
    "/admin/users",
    response_model=UserListResponse,
)
async def get_user_list(
    search: str | None = Query(default=None),
    department: DepartmentEnum | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(async_get_db),
    current_admin: User = Depends(get_current_admin),
):
    users, total = await get_users(
        db=db,
        search=search,
        department=department,
        page=page,
        size=size,
    )

    return UserListResponse(
        items=users,
        page=page,
        size=size,
        total=total,
        total_pages=math.ceil(total / size),
    )


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=UserRoleResponse,
)
async def update_user_role_api(
    user_id: uuid_pkg.UUID,
    payload: UserRoleUpdateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_admin: User = Depends(get_current_admin),
):
    target_user = await get_user_by_id(db, user_id)

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회원을 찾을 수 없습니다.",
        )

    return await change_user_role(
        db=db,
        target_user=target_user,
        new_role=payload.role,
    )


@router.patch(
    "/users/me",
    response_model=UserResponse,
)
async def update_my_info(
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    return await change_my_info(
        db=db,
        current_user=current_user,
        department=payload.department,
        phone_number=payload.phone_number,
    )


@router.patch(
    "/users/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_my_password(
    payload: PasswordChangeRequest,
    response: Response,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    await change_my_password(
        db=db,
        current_user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )

    response.delete_cookie("refresh_token")
    return None


@router.delete(
    "/users/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_account(
    response: Response,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    await withdraw_user(
        db=db,
        current_user=current_user,
    )

    response.delete_cookie("refresh_token")
    return None