"""폐렴 예측 실행/조회 서비스.

REQ-PRED-001 / REQ-PRED-002 및 `docs/6일차_폐렴예측_API_설계.md` 를 구현한다.
"""

import logging
import uuid as uuid_pkg
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis_result import AiAnalysisResult
from app.repositories.ai_prediction_repository import (
    create_ai_result,
    get_ai_result_by_record_and_model,
    get_ai_results_by_patient,
    get_latest_xray_by_record,
)
from app.services.medical_record_service import find_medical_record_or_404
from app.services.patient_service import find_patient_or_404

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIRECTORY = (BASE_DIR / "media").resolve()

# worker/model.py 의 AI_MODEL_NAME 과 반드시 동일해야 한다.
# (캐시 키가 record_id + 이 문자열 조합이므로 불일치 시 캐시가 동작하지 않는다.
#  test/test_ai_prediction.py 에서 두 값이 같은지 검증한다.)
AI_MODEL_NAME = "SimpleCNN"


def _resolve_local_xray_path(image_url: str) -> Path:
    """DB에 저장된 `/media/...` 상대 URL을 로컬 파일 경로로 변환한다.

    media 디렉터리 밖을 가리키거나 실제 파일이 없으면 500으로 처리한다.
    (DB 행은 있는데 파일이 유실된 경우는 서버 측 무결성 문제이다.)
    """
    relative_path = image_url.lstrip("/\\")
    local_path = (BASE_DIR / relative_path).resolve()

    if (
        local_path != MEDIA_DIRECTORY
        and MEDIA_DIRECTORY not in local_path.parents
    ):
        logger.error("허용되지 않은 X-Ray 경로입니다: %s", image_url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="X-Ray 이미지 경로가 올바르지 않습니다.",
        )

    if not local_path.is_file():
        logger.error("X-Ray 이미지 파일을 찾을 수 없습니다: %s", local_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="X-Ray 이미지 파일을 찾을 수 없습니다.",
        )

    return local_path


async def run_pneumonia_prediction(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    record_id: uuid_pkg.UUID,
) -> tuple[AiAnalysisResult, bool]:
    """폐렴 예측을 실행하거나, 이미 저장된 결과가 있으면 그대로 반환한다.

    Returns:
        (예측 결과, 캐시 사용 여부). 캐시 사용 시 두 번째 값이 True.
    """
    # 1. 환자 존재 + 진료기록이 그 환자 소유인지 확인 (아니면 404)
    await find_medical_record_or_404(
        db=db,
        patient_id=patient_id,
        record_id=record_id,
    )

    # 2. 캐시 조회 — 추론보다 먼저 수행해 히트 시 모델 로딩/추론을 생략한다.
    cached = await get_ai_result_by_record_and_model(
        db=db,
        record_id=record_id,
        ai_model=AI_MODEL_NAME,
    )

    if cached is not None:
        return cached, True

    # 3. 추론 대상 X-Ray 결정 (여러 장이면 촬영일시가 가장 최신인 1장)
    xray = await get_latest_xray_by_record(
        db=db,
        record_id=record_id,
    )

    if xray is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="진료기록에 X-Ray 이미지가 없어 예측을 실행할 수 없습니다.",
        )

    image_path = _resolve_local_xray_path(xray.image_url)

    # 4. 추론 실행 — torch 는 여기서 지연 import (캐시 히트 경로에서는 로딩하지 않음)
    try:
        from worker.model import AI_MODEL_NAME as WORKER_MODEL_NAME
        from worker.model import predict

        prediction = await run_in_threadpool(predict, image_path)
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("폐렴 예측 추론에 실패했습니다. record_id=%s", record_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 모델 추론 중 오류가 발생했습니다.",
        ) from error

    # 5. 결과 저장 (heatmap 생성은 이번 단계 범위 밖 → None)
    ai_result = await create_ai_result(
        db=db,
        record_id=record_id,
        is_pneumonia=prediction.is_pneumonia,
        confidence=prediction.confidence,
        ai_model=WORKER_MODEL_NAME,
        heatmap_url=None,
    )

    return ai_result, False


async def list_patient_predictions(
    db: AsyncSession,
    patient_id: uuid_pkg.UUID,
    page: int,
    size: int,
) -> tuple[list[tuple[AiAnalysisResult, str]], int]:
    """환자별 예측 결과 목록을 조회한다. 환자가 없으면 404."""
    await find_patient_or_404(
        db=db,
        patient_id=patient_id,
    )

    return await get_ai_results_by_patient(
        db=db,
        patient_id=patient_id,
        page=page,
        size=size,
    )
