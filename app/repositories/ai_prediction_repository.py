import uuid as uuid_pkg
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis_result import AiAnalysisResult
from app.models.medical_record import MedicalRecord
from app.models.xray_image import XrayImage


async def get_ai_result_by_record_and_model(
    db: AsyncSession,
    record_id: uuid_pkg.UUID,
    ai_model: str,
) -> AiAnalysisResult | None:
    """같은 진료기록 + 같은 모델로 저장된 예측 결과(캐시)를 조회한다."""
    query = select(AiAnalysisResult).where(
        AiAnalysisResult.record_id == str(record_id),
        AiAnalysisResult.ai_model == ai_model,
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


async def get_latest_xray_by_record(
    db: AsyncSession,
    record_id: uuid_pkg.UUID,
) -> XrayImage | None:
    """진료기록에 등록된 X-Ray 중 촬영일시가 가장 최신인 1장을 조회한다."""
    query = (
        select(XrayImage)
        .where(XrayImage.record_id == str(record_id))
        .order_by(XrayImage.shooting_datetime.desc())
        .limit(1)
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


async def create_ai_result(
    db: AsyncSession,
    record_id: uuid_pkg.UUID,
    is_pneumonia: bool,
    confidence: float,
    ai_model: str,
    heatmap_url: str | None = None,
) -> AiAnalysisResult:
    """새 예측 결과를 저장하고 커밋한다."""
    ai_result = AiAnalysisResult(
        record_id=str(record_id),
        is_pneumonia=is_pneumonia,
        confidence=Decimal(str(confidence)),
        ai_model=ai_model,
        heatmap_url=heatmap_url,
    )

    db.add(ai_result)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(ai_result)

    return ai_result


async def get_ai_results_by_patient(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    page: int,
    size: int,
) -> tuple[list[tuple[AiAnalysisResult, str]], int]:
    """환자의 모든 진료기록에 대한 예측 결과를 최신순으로 페이지 조회한다.

    반환값 각 항목은 `(AiAnalysisResult, chart_number)` 튜플이다.
    """
    join_condition = AiAnalysisResult.record_id == MedicalRecord.uuid
    patient_condition = MedicalRecord.patient_id == str(patient_id)

    count_query = (
        select(func.count())
        .select_from(AiAnalysisResult)
        .join(MedicalRecord, join_condition)
        .where(patient_condition)
    )

    total = await db.scalar(count_query)

    rows_query = (
        select(AiAnalysisResult, MedicalRecord.chart_number)
        .join(MedicalRecord, join_condition)
        .where(patient_condition)
        .order_by(AiAnalysisResult.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    result = await db.execute(rows_query)
    rows = [(row[0], row[1]) for row in result.all()]

    return rows, total or 0
