import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel

from app.models.ai_analysis_result import AiAnalysisResult


def _label(is_pneumonia: bool) -> str:
    """is_pneumonia 값을 API 응답용 라벨 문자열로 변환한다."""
    return "PNEUMONIA" if is_pneumonia else "NORMAL"


class AiPredictionResponse(BaseModel):
    """폐렴 예측 실행/조회(POST) 응답.

    DB 컬럼과 필드명이 다른 부분(`medical_record_id`, `heatmap_image_url`,
    `predicted_at`)과 파생 필드(`label`, `from_cache`)는 `from_result()`에서 매핑한다.
    """

    id: uuid_pkg.UUID
    medical_record_id: uuid_pkg.UUID
    is_pneumonia: bool
    label: str
    confidence: float
    heatmap_image_url: str | None
    ai_model: str
    predicted_at: datetime
    from_cache: bool

    @classmethod
    def from_result(
        cls,
        result: AiAnalysisResult,
        from_cache: bool,
    ) -> "AiPredictionResponse":
        return cls(
            id=result.uuid,
            medical_record_id=result.record_id,
            is_pneumonia=result.is_pneumonia,
            label=_label(result.is_pneumonia),
            confidence=float(result.confidence),
            heatmap_image_url=result.heatmap_url,
            ai_model=result.ai_model,
            predicted_at=result.created_at,
            from_cache=from_cache,
        )


class AiPredictionListItem(BaseModel):
    """환자별 예측 결과 목록(GET)의 개별 항목."""

    id: uuid_pkg.UUID
    medical_record_id: uuid_pkg.UUID
    chart_number: str
    is_pneumonia: bool
    confidence: float
    heatmap_image_url: str | None
    ai_model: str
    predicted_at: datetime

    @classmethod
    def from_row(
        cls,
        result: AiAnalysisResult,
        chart_number: str,
    ) -> "AiPredictionListItem":
        return cls(
            id=result.uuid,
            medical_record_id=result.record_id,
            chart_number=chart_number,
            is_pneumonia=result.is_pneumonia,
            confidence=float(result.confidence),
            heatmap_image_url=result.heatmap_url,
            ai_model=result.ai_model,
            predicted_at=result.created_at,
        )


class AiPredictionListResponse(BaseModel):
    items: list[AiPredictionListItem]
    page: int
    size: int
    total: int
    total_pages: int
