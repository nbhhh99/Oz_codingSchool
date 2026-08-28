import uuid as uuid_pkg
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medical_record import MedicalRecord
from app.models.user import User
from app.repositories.medical_record_repository import (
    create_medical_record_with_xray,
    get_medical_record_by_chart_number,
    get_medical_record_detail,
)
from app.services.patient_service import find_patient_or_404


BASE_DIR = Path(__file__).resolve().parent.parent.parent
XRAY_DIRECTORY = BASE_DIR / "media" / "xrays"

MAX_IMAGE_SIZE = 10 * 1024 * 1024

JPEG_SIGNATURE = b"\xff\xd8\xff"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def detect_image_extension(content: bytes) -> str | None:
    if content.startswith(JPEG_SIGNATURE):
        return ".jpg"

    if content.startswith(PNG_SIGNATURE):
        return ".png"

    return None


async def save_xray_image(
    xray_image: UploadFile,
) -> tuple[str, Path]:
    content = await xray_image.read(MAX_IMAGE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Ray 이미지 파일이 비어 있습니다.",
        )

    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Ray 이미지는 10MB를 초과할 수 없습니다.",
        )

    extension = detect_image_extension(content)

    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JPEG 또는 PNG 이미지만 업로드할 수 있습니다.",
        )

    now = datetime.now(UTC)

    relative_directory = Path(
        str(now.year),
        f"{now.month:02d}",
        f"{now.day:02d}",
    )

    save_directory = XRAY_DIRECTORY / relative_directory
    save_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_name = f"{uuid_pkg.uuid4()}{extension}"
    absolute_path = save_directory / file_name

    try:
        absolute_path.write_bytes(content)
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="X-Ray 이미지를 저장하지 못했습니다.",
        ) from error
    finally:
        await xray_image.close()

    relative_url = (
        Path("/media/xrays")
        / relative_directory
        / file_name
    ).as_posix()

    return relative_url, absolute_path


async def register_medical_record(
    db: AsyncSession,
    current_user: User,
    patient_id: uuid_pkg.UUID,
    chart_number: str,
    symptoms: str,
    xray_image: UploadFile,
    shooting_datetime: datetime | None,
) -> dict:
    await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )

    normalized_chart_number = chart_number.strip()
    normalized_symptoms = symptoms.strip()

    if not normalized_chart_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="진료 차트 넘버를 입력해야 합니다.",
        )

    if len(normalized_chart_number) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="진료 차트 넘버는 50자를 초과할 수 없습니다.",
        )

    if not normalized_symptoms:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="증상을 입력해야 합니다.",
        )

    existing_record = await get_medical_record_by_chart_number(
        db=db,
        chart_number=normalized_chart_number,
    )

    if existing_record is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 진료 차트 넘버입니다.",
        )

    image_url, absolute_path = await save_xray_image(
        xray_image=xray_image,
    )

    if shooting_datetime is None:
        shooting_datetime = datetime.now(UTC)

    try:
        medical_record, saved_xray = (
            await create_medical_record_with_xray(
                db=db,
                patient_id=patient_id,
                uploader_id=current_user.uuid,
                chart_number=normalized_chart_number,
                symptoms=normalized_symptoms,
                image_url=image_url,
                shooting_datetime=shooting_datetime,
            )
        )
    except IntegrityError as error:
        absolute_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 진료 차트 넘버입니다.",
        ) from error
    except Exception:
        absolute_path.unlink(missing_ok=True)
        raise

    return {
        "uuid": medical_record.uuid,
        "patient_id": medical_record.patient_id,
        "chart_number": medical_record.chart_number,
        "symptoms": medical_record.symptoms,
        "xray_image": saved_xray,
        "created_at": medical_record.created_at,
    }


async def find_medical_record_or_404(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    record_id: uuid_pkg.UUID,
) -> MedicalRecord:
    await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )

    medical_record = await get_medical_record_detail(
        db=db,
        patient_id=patient_id,
        record_id=record_id,
    )

    if medical_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="진료기록을 찾을 수 없습니다.",
        )

    return medical_record