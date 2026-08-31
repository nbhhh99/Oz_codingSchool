"""AI 예측 - 순수 단위 테스트 (DB / 앱 불필요)."""

import uuid as uuid_pkg
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.models.ai_analysis_result import AiAnalysisResult
from app.schemas.ai_prediction import AiPredictionListItem, AiPredictionResponse
from app.services import ai_prediction_service as svc


def _make_result(is_pneumonia: bool = True) -> AiAnalysisResult:
    r = AiAnalysisResult(
        record_id=str(uuid_pkg.uuid4()),
        is_pneumonia=is_pneumonia,
        confidence=94.32,
        ai_model="SimpleCNN",
        heatmap_url=None,
    )
    r.uuid = str(uuid_pkg.uuid4())
    r.created_at = datetime(2026, 8, 31, 10, 20, tzinfo=UTC)
    return r


def test_model_name_matches_worker():
    """서비스 상수와 worker 상수가 어긋나면 캐시가 깨진다."""
    pytest.importorskip("torch", reason="worker.model 은 torch 필요")
    from worker.model import AI_MODEL_NAME as WORKER_NAME

    assert svc.AI_MODEL_NAME == WORKER_NAME == "SimpleCNN"


def test_response_mapping_pneumonia():
    resp = AiPredictionResponse.from_result(_make_result(True), from_cache=False)

    assert resp.is_pneumonia is True
    assert resp.label == "PNEUMONIA"
    assert resp.confidence == 94.32
    assert resp.heatmap_image_url is None
    assert resp.from_cache is False
    assert resp.predicted_at.year == 2026


def test_response_mapping_normal_and_cache_flag():
    resp = AiPredictionResponse.from_result(_make_result(False), from_cache=True)

    assert resp.is_pneumonia is False
    assert resp.label == "NORMAL"
    assert resp.from_cache is True


def test_list_item_mapping_includes_chart_number():
    item = AiPredictionListItem.from_row(_make_result(True), "CHART-20260828-001")

    assert item.chart_number == "CHART-20260828-001"
    assert not hasattr(item, "from_cache")  # 목록 항목에는 없음
    assert not hasattr(item, "label")


def test_resolve_local_xray_path_rejects_traversal():
    with pytest.raises(HTTPException) as exc:
        svc._resolve_local_xray_path("/media/../../etc/passwd")
    assert exc.value.status_code == 500


def test_resolve_local_xray_path_missing_file():
    with pytest.raises(HTTPException) as exc:
        svc._resolve_local_xray_path("/media/xrays/does/not/exist.png")
    assert exc.value.status_code == 500
