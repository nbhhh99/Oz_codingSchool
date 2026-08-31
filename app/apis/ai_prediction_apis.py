import math
import uuid as uuid_pkg

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.models.user import User
from app.schemas.ai_prediction import (
    AiPredictionListItem,
    AiPredictionListResponse,
    AiPredictionResponse,
)
from app.services.ai_prediction_service import (
    list_patient_predictions,
    run_pneumonia_prediction,
)
from app.services.patient_service import get_current_staff

router = APIRouter(
    prefix="/api/v1/patients",
    tags=["AI Prediction"],
)


@router.post(
    "/{patient_id}/medical-records/{record_id}/ai-prediction",
    response_model=AiPredictionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_ai_prediction_api(
    patient_id: uuid_pkg.UUID,
    record_id: uuid_pkg.UUID,
    response: Response,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    result, from_cache = await run_pneumonia_prediction(
        db=db,
        patient_id=patient_id,
        record_id=record_id,
    )

    # 저장된 결과를 그대로 반환한 경우 200, 새로 추론·저장한 경우 201
    if from_cache:
        response.status_code = status.HTTP_200_OK

    return AiPredictionResponse.from_result(result, from_cache=from_cache)


@router.get(
    "/{patient_id}/ai-predictions",
    response_model=AiPredictionListResponse,
)
async def get_ai_prediction_list_api(
    patient_id: uuid_pkg.UUID,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_staff),
):
    rows, total = await list_patient_predictions(
        db=db,
        patient_id=patient_id,
        page=page,
        size=size,
    )

    return AiPredictionListResponse(
        items=[
            AiPredictionListItem.from_row(result, chart_number)
            for result, chart_number in rows
        ],
        page=page,
        size=size,
        total=total,
        total_pages=math.ceil(total / size) if total else 0,
    )
