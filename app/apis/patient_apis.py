import math
import uuid as uuid_pkg
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.models.user import User
from app.repositories.patient_repository import get_patients
from app.schemas.patient import (
    PatientCreateRequest,
    PatientListResponse,
    PatientResponse,
    PatientUpdateRequest,
)
from app.services.patient_service import (
    change_patient_info,
    find_patient_or_404,
    get_current_medical_staff,
    get_current_staff,
    register_patient,
    remove_patient,
)


router = APIRouter(
    prefix="/api/v1/patients",
    tags=["Patient Management"],
)


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_patient_api(
    payload: PatientCreateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_medical_staff),
):
    return await register_patient(
        db=db,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        phone=payload.phone,
    )


@router.get(
    "",
    response_model=PatientListResponse,
)
async def get_patient_list(
    search: str | None = Query(default=None),
    gender: Literal["male", "female"] | None = Query(default=None),
    min_age: int | None = Query(default=None, ge=0, le=150),
    max_age: int | None = Query(default=None, ge=0, le=150),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    if (
        min_age is not None
        and max_age is not None
        and min_age > max_age
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="최소 나이는 최대 나이보다 클 수 없습니다.",
        )

    patients, total = await get_patients(
        db=db,
        search=search,
        gender=gender,
        min_age=min_age,
        max_age=max_age,
        page=page,
        size=size,
    )

    return PatientListResponse(
        items=patients,
        page=page,
        size=size,
        total=total,
        total_pages=math.ceil(total / size),
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
)
async def get_patient_detail(
    patient_id: uuid_pkg.UUID,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    return await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
)
async def update_patient_api(
    patient_id: uuid_pkg.UUID,
    payload: PatientUpdateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    patient = await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )

    return await change_patient_info(
        db=db,
        patient=patient,
        name=payload.name,
        phone=payload.phone,
    )


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_patient_api(
    patient_id: uuid_pkg.UUID,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    patient = await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )

    await remove_patient(
        db=db,
        patient=patient,
    )

    return None