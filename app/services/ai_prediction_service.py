"""폐렴 예측 실행/조회 서비스.

REQ-PRED-001 / REQ-PRED-002 및 `docs/6일차_폐렴예측_API_설계.md` 를 구현하고,
`docs/9일차_동시성문제_해결을위한_아키텍처설계.md` 의 Event-Driven Architecture 에 따라
**추론은 별도 워커 프로세스에 위임**한다.

흐름 (POST /ai-prediction):
    1. 진료기록/환자 검증
    2. DB 캐시 조회 — (record_id, ai_model) 결과가 있으면 그대로 반환 (추론 생략)
    3. 대상 X-Ray 결정 + 경로 검증
    4. Redis 작업 큐에 작업 LPUSH → 결과 채널 SUBSCRIBE 로 워커 응답 대기
       (torch 는 이 프로세스에서 import 하지 않는다)
    5. 받은 결과를 DB 에 저장하고 응답
"""

import asyncio
import json
import logging
import uuid as uuid_pkg
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis
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
#  tests/test_ai_prediction_unit.py 에서 두 값이 같은지 검증한다.)
AI_MODEL_NAME = "SimpleCNN"


@dataclass
class PredictionPayload:
    """워커가 Pub/Sub 로 돌려준 추론 결과 (DB 저장 직전 형태)."""

    is_pneumonia: bool
    confidence: float
    ai_model: str


def _resolve_local_xray_path(image_url: str) -> Path:
    """DB에 저장된 `/media/...` 상대 URL을 로컬 파일 경로로 변환한다.

    media 디렉터리 밖을 가리키거나 실제 파일이 없으면 500으로 처리한다.
    (DB 행은 있는데 파일이 유실된 경우는 서버 측 무결성 문제이다.)

    실제 이미지 로딩은 워커가 공유 media 볼륨에서 수행하지만, 여기서 먼저
    검증해 잘못된 요청이면 큐에 넣기 전에 빠르게 실패시킨다.
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


@asynccontextmanager
async def _prediction_lock(record_id: uuid_pkg.UUID):
    """같은 (record_id, 모델) 조합의 추론이 동시에 여러 번 돌지 않도록 직렬화한다.

    (선택 요구사항 — 동시 요청 문제 해결) 여러 요청이 동시에 캐시 미스로 들어와도
    Redis 분산 잠금으로 한 번에 하나만 큐에 넣게 하고, 잠금을 얻은 뒤 캐시를
    재확인해(run_pneumonia_prediction 참고) 중복 추론과 중복 저장을 피한다.
    """
    redis_client = get_redis()
    lock = redis_client.lock(
        f"pneumonia:lock:{record_id}:{AI_MODEL_NAME}",
        timeout=settings.PREDICTION_TIMEOUT_SECONDS + 15,
        blocking=True,
        blocking_timeout=settings.PREDICTION_TIMEOUT_SECONDS + 15,
    )
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            try:
                await lock.release()
            except Exception:  # noqa: BLE001 - 잠금이 이미 만료된 경우 등
                logger.warning("추론 잠금 해제 실패 record_id=%s", record_id)


async def request_prediction(record_id: str, image_url: str) -> PredictionPayload:
    """Redis 작업 큐에 추론 작업을 넣고, 결과 채널을 구독해 워커 응답을 기다린다.

    `SUBSCRIBE` 는 구독 이후 발행된 메시지만 받으므로, **결과 채널을 먼저 구독한 뒤**
    작업을 큐에 넣는다. `settings.PREDICTION_TIMEOUT_SECONDS` 안에 응답이 없으면 503.
    """
    redis_client = get_redis()
    job_id = str(uuid_pkg.uuid4())
    result_channel = f"pneumonia:result:{job_id}"

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(result_channel)
    try:
        task = json.dumps(
            {
                "job_id": job_id,
                "record_id": record_id,
                "image_url": image_url,
                "ai_model": AI_MODEL_NAME,
                "result_channel": result_channel,
            }
        )
        await redis_client.lpush(settings.PREDICTION_QUEUE_KEY, task)
        logger.info(
            "폐렴 예측 작업 적재: job_id=%s record_id=%s queue=%s",
            job_id,
            record_id,
            settings.PREDICTION_QUEUE_KEY,
        )

        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.PREDICTION_TIMEOUT_SECONDS
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                logger.error("워커 응답 대기 시간 초과: job_id=%s", job_id)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="AI 추론 결과를 기다리는 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
                )

            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=min(remaining, 1.0),
            )
            if message is None:
                continue

            data = json.loads(message["data"])
            if data.get("status") == "error":
                logger.error(
                    "워커가 추론 실패를 보고함: job_id=%s detail=%s",
                    job_id,
                    data.get("detail"),
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="AI 모델 추론 중 오류가 발생했습니다.",
                )

            return PredictionPayload(
                is_pneumonia=bool(data["is_pneumonia"]),
                confidence=float(data["confidence"]),
                ai_model=str(data.get("ai_model") or AI_MODEL_NAME),
            )
    finally:
        try:
            await pubsub.unsubscribe(result_channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 - 정리 실패는 요청 처리에 영향 없음
            pass


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

    # 2. 캐시 조회 — 추론보다 먼저 수행해 히트 시 큐 적재/추론을 생략한다.
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

    # 잘못된 경로/유실 파일이면 큐에 넣기 전에 빠르게 실패시킨다.
    _resolve_local_xray_path(xray.image_url)

    # 4. 추론을 워커에 위임 — 큐 적재 + 결과 구독. 동시 요청은 잠금으로 직렬화한다.
    async with _prediction_lock(record_id):
        cached = await get_ai_result_by_record_and_model(
            db=db,
            record_id=record_id,
            ai_model=AI_MODEL_NAME,
        )
        if cached is not None:
            return cached, True

        payload = await request_prediction(
            record_id=str(record_id),
            image_url=xray.image_url,
        )

    # 5. 결과 저장 (heatmap 생성은 이번 단계 범위 밖 → None)
    ai_result = await create_ai_result(
        db=db,
        record_id=record_id,
        is_pneumonia=payload.is_pneumonia,
        confidence=payload.confidence,
        ai_model=payload.ai_model,
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
