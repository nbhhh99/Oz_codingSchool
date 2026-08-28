import uuid as uuid_pkg

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.user import DepartmentEnum, RoleEnum, User
from app.repositories.patient_repository import (
    create_patient,
    delete_patient,
    get_patient_by_id,
    update_patient,
)
from app.services.auth_service import get_current_user


async def get_current_staff(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성 계정은 접근할 수 없습니다.",
        )

    if current_user.role not in (
        RoleEnum.STAFF,
        RoleEnum.ADMIN,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="스태프 또는 관리자 권한이 필요합니다.",
        )

    return current_user


async def get_current_medical_staff(
    current_user: User = Depends(get_current_staff),
) -> User:
    if current_user.department != DepartmentEnum.MEDICAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="의료 부서 사용자만 등록할 수 있습니다.",
        )

    return current_user


async def find_patient_or_404(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
) -> Patient:
    patient = await get_patient_by_id(
        db=db,
        patient_id=patient_id,
    )

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="환자를 찾을 수 없습니다.",
        )

    return patient


async def register_patient(
    db: AsyncSession,
    name: str,
    age: int,
    gender: str,
    phone: str,
) -> Patient:
    return await create_patient(
        db=db,
        name=name,
        age=age,
        gender=gender,
        phone=phone,
    )


async def change_patient_info(
    db: AsyncSession,
    patient: Patient,
    name: str | None,
    phone: str | None,
) -> Patient:
    return await update_patient(
        db=db,
        patient=patient,
        name=name,
        phone=phone,
    )


async def remove_patient(
    db: AsyncSession,
    patient: Patient,
) -> None:
    await delete_patient(
        db=db,
        patient=patient,
    )