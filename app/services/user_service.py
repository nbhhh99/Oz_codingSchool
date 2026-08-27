from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import DepartmentEnum, RoleEnum, User
from app.repositories.user_repository import (
    count_active_admins,
    delete_user,
    get_user_by_phone_number,
    update_user_info,
    update_user_password,
    update_user_role,
)
from app.services.auth_service import (
    get_current_user,
    hash_password,
    verify_password,
)


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )

    return current_user


async def change_user_role(
    db: AsyncSession,
    target_user: User,
    new_role: RoleEnum,
) -> User:
    if (
        target_user.role == RoleEnum.ADMIN
        and new_role != RoleEnum.ADMIN
    ):
        admin_count = await count_active_admins(db)

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="마지막 관리자의 권한은 변경할 수 없습니다.",
            )

    return await update_user_role(
        db=db,
        user=target_user,
        role=new_role,
    )


async def change_my_info(
    db: AsyncSession,
    current_user: User,
    department: DepartmentEnum | None,
    phone_number: str | None,
) -> User:
    if phone_number is not None:
        existing_user = await get_user_by_phone_number(
            db,
            phone_number,
        )

        if (
            existing_user is not None
            and existing_user.uuid != current_user.uuid
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 사용 중인 휴대폰 번호입니다.",
            )

    return await update_user_info(
        db=db,
        user=current_user,
        department=department,
        phone_number=phone_number,
    )


async def change_my_password(
    db: AsyncSession,
    current_user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(
        current_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="기존 비밀번호가 일치하지 않습니다.",
        )

    if verify_password(
        new_password,
        current_user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="새 비밀번호는 기존 비밀번호와 달라야 합니다.",
        )

    await update_user_password(
        db=db,
        user=current_user,
        hashed_password=hash_password(new_password),
    )


async def withdraw_user(
    db: AsyncSession,
    current_user: User,
) -> None:
    if current_user.role == RoleEnum.ADMIN:
        admin_count = await count_active_admins(db)

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="마지막 관리자는 탈퇴할 수 없습니다.",
            )

    await delete_user(
        db=db,
        user=current_user,
    )