import math
import uuid as uuid_pkg
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.models.user import User
from app.repositories.medical_record_repository import (
    get_medical_records_by_patient,
)
from app.schemas.medical_record import (
    MedicalRecordCreateResponse,
    MedicalRecordDetailResponse,
    MedicalRecordListResponse,
)
from app.services.medical_record_service import (
    find_medical_record_or_404,
    register_medical_record,
)
from app.services.patient_service import (
    find_patient_or_404,
    get_current_medical_staff,
    get_current_staff,
)


router = APIRouter(
    prefix="/api/v1/patients/{patient_id}/medical-records",
    tags=["Medical Records"],
)


@router.post(
    "",
    response_model=MedicalRecordCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_medical_record_api(
    patient_id: uuid_pkg.UUID,
    chart_number: str = Form(...),
    symptoms: str = Form(...),
    xray_image: UploadFile = File(...),
    shooting_datetime: datetime | None = Form(default=None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_medical_staff),
):
    return await register_medical_record(
        db=db,
        current_user=current_user,
        patient_id=patient_id,
        chart_number=chart_number,
        symptoms=symptoms,
        xray_image=xray_image,
        shooting_datetime=shooting_datetime,
    )


@router.get(
    "",
    response_model=MedicalRecordListResponse,
)
async def get_medical_record_list(
    patient_id: uuid_pkg.UUID,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )

    records, total = await get_medical_records_by_patient(
        db=db,
        patient_id=patient_id,
        page=page,
        size=size,
    )

    return MedicalRecordListResponse(
        items=records,
        page=page,
        size=size,
        total=total,
        total_pages=math.ceil(total / size),
    )


@router.get(
    "/{record_id}",
    response_model=MedicalRecordDetailResponse,
)
async def get_medical_record_detail_api(
    patient_id: uuid_pkg.UUID,
    record_id: uuid_pkg.UUID,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    return await find_medical_record_or_404(
        db=db,
        patient_id=patient_id,
        record_id=record_id,
    )