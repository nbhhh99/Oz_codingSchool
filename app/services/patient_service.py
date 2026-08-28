import logging
import uuid as uuid_pkg
from pathlib import Path

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.user import DepartmentEnum, RoleEnum, User
from app.repositories.medical_record_repository import (
    get_xray_image_urls_by_patient,
)
from app.repositories.patient_repository import (
    create_patient,
    delete_patient,
    get_patient_by_id,
    update_patient,
)
from app.services.auth_service import get_current_user


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIRECTORY = (BASE_DIR / "media").resolve()


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
    image_urls = await get_xray_image_urls_by_patient(
        db=db,
        patient_id=patient.uuid,
    )

    # DB 삭제에 실패하면 실제 이미지 파일을 남겨둡니다.
    await delete_patient(
        db=db,
        patient=patient,
    )

    # DB 삭제 성공 후 로컬 X-Ray 파일을 정리합니다.
    for image_url in image_urls:
        relative_path = image_url.lstrip("/\\")
        image_path = (BASE_DIR / relative_path).resolve()

        # media 디렉터리 밖의 파일은 삭제하지 않습니다.
        if (
            image_path != MEDIA_DIRECTORY
            and MEDIA_DIRECTORY not in image_path.parents
        ):
            logger.warning(
                "허용되지 않은 X-Ray 삭제 경로입니다: %s",
                image_url,
            )
            continue

        try:
            image_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(
                "X-Ray 이미지 파일을 삭제하지 못했습니다: %s",
                image_path,
            )