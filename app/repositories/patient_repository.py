import uuid as uuid_pkg

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient


async def create_patient(
    db: AsyncSession,
    name: str,
    age: int,
    gender: str,
    phone: str,
) -> Patient:
    patient = Patient(
        name=name,
        age=age,
        gender=gender,
        phone=phone,
    )

    db.add(patient)
    await db.commit()
    await db.refresh(patient)

    return patient


async def get_patient_by_id(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
) -> Patient | None:
    query = select(Patient).where(
        Patient.uuid == str(patient_id)
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


async def get_patients(
    db: AsyncSession,
    search: str | None,
    gender: str | None,
    min_age: int | None,
    max_age: int | None,
    page: int,
    size: int,
) -> tuple[list[Patient], int]:
    conditions = []

    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            Patient.name.ilike(search_pattern)
        )

    if gender:
        conditions.append(
            Patient.gender == gender
        )

    if min_age is not None:
        conditions.append(
            Patient.age >= min_age
        )

    if max_age is not None:
        conditions.append(
            Patient.age <= max_age
        )

    count_query = (
        select(func.count())
        .select_from(Patient)
        .where(*conditions)
    )

    total = await db.scalar(count_query)

    patients_query = (
        select(Patient)
        .where(*conditions)
        .order_by(Patient.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    result = await db.execute(patients_query)
    patients = list(result.scalars().all())

    return patients, total or 0


async def update_patient(
    db: AsyncSession,
    patient: Patient,
    name: str | None,
    phone: str | None,
) -> Patient:
    if name is not None:
        patient.name = name

    if phone is not None:
        patient.phone = phone

    await db.commit()
    await db.refresh(patient)

    return patient


async def delete_patient(
    db: AsyncSession,
    patient: Patient,
) -> None:
    await db.delete(patient)
    await db.commit()