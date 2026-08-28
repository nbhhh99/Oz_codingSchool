import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.medical_record import MedicalRecord
from app.models.xray_image import XrayImage


async def get_medical_record_by_chart_number(
    db: AsyncSession,
    chart_number: str,
) -> MedicalRecord | None:
    query = select(MedicalRecord).where(
        MedicalRecord.chart_number == chart_number
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


async def create_medical_record_with_xray(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    uploader_id: uuid_pkg.UUID,
    chart_number: str,
    symptoms: str,
    image_url: str,
    shooting_datetime: datetime,
) -> tuple[MedicalRecord, XrayImage]:
    medical_record = MedicalRecord(
        patient_id=str(patient_id),
        chart_number=chart_number,
        symptoms=symptoms,
    )

    db.add(medical_record)

    # X-Ray가 참조할 진료기록 UUID를 먼저 생성합니다.
    await db.flush()

    xray_image = XrayImage(
        record_id=str(medical_record.uuid),
        uploader_id=str(uploader_id),
        image_url=image_url,
        shooting_datetime=shooting_datetime,
    )

    db.add(xray_image)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(medical_record)
    await db.refresh(xray_image)

    return medical_record, xray_image


async def get_medical_records_by_patient(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    page: int,
    size: int,
) -> tuple[list[MedicalRecord], int]:
    condition = (
        MedicalRecord.patient_id == str(patient_id)
    )

    count_query = (
        select(func.count())
        .select_from(MedicalRecord)
        .where(condition)
    )

    total = await db.scalar(count_query)

    records_query = (
        select(MedicalRecord)
        .where(condition)
        .order_by(MedicalRecord.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    result = await db.execute(records_query)
    records = list(result.scalars().all())

    return records, total or 0


async def get_medical_record_detail(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    record_id: uuid_pkg.UUID,
) -> MedicalRecord | None:
    query = (
        select(MedicalRecord)
        .options(
            selectinload(MedicalRecord.xray_images)
        )
        .where(
            MedicalRecord.uuid == str(record_id),
            MedicalRecord.patient_id == str(patient_id),
        )
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


async def get_xray_image_urls_by_patient(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
) -> list[str]:
    query = (
        select(XrayImage.image_url)
        .join(
            MedicalRecord,
            XrayImage.record_id == MedicalRecord.uuid,
        )
        .where(
            MedicalRecord.patient_id == str(patient_id)
        )
    )

    result = await db.execute(query)

    return list(result.scalars().all())