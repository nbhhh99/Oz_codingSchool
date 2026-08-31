"""AI 예측 API 통합 테스트 (SQLite + ASGI).

`worker.model.predict` 는 스텁으로 대체하고, X-Ray 로컬 경로 검증은 우회한다.
검증 대상은 라우터/서비스/리포지토리/DB 및 캐시·상태코드 분기 로직이다.
"""

import sys
import types
import uuid as uuid_pkg
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import ai_prediction_service as svc

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _stub_worker(monkeypatch):
    """`worker.model` 을 가짜 모듈로 대체한다.

    이렇게 하면 torch 미설치 환경에서도 API 테스트가 돌아간다.
    (서비스는 추론 시점에 `from worker.model import predict` 로 지연 import 한다.)
    """

    def fake_predict(_image):
        return SimpleNamespace(
            is_pneumonia=True,
            label="PNEUMONIA",
            confidence=91.5,
            probabilities={"NORMAL": 0.085, "PNEUMONIA": 0.915},
            ai_model="SimpleCNN",
        )

    fake_module = types.ModuleType("worker.model")
    fake_module.predict = fake_predict
    fake_module.AI_MODEL_NAME = "SimpleCNN"
    monkeypatch.setitem(sys.modules, "worker.model", fake_module)

    monkeypatch.setattr(
        svc, "_resolve_local_xray_path", lambda _url: Path("/tmp/fake.png")
    )


async def test_run_prediction_creates_then_caches(client, seeded_record):
    base = f"/api/v1/patients/{seeded_record['patient_id']}/medical-records/{seeded_record['record_id']}/ai-prediction"

    first = await client.post(base)
    assert first.status_code == 201
    body = first.json()
    assert body["is_pneumonia"] is True
    assert body["label"] == "PNEUMONIA"
    assert body["confidence"] == 91.5
    assert body["ai_model"] == "SimpleCNN"
    assert body["heatmap_image_url"] is None
    assert body["from_cache"] is False
    assert body["medical_record_id"] == seeded_record["record_id"]

    second = await client.post(base)
    assert second.status_code == 200
    body2 = second.json()
    assert body2["from_cache"] is True
    assert body2["id"] == body["id"]  # 같은 저장 결과


async def test_run_prediction_record_not_found(client, seeded_record):
    url = f"/api/v1/patients/{seeded_record['patient_id']}/medical-records/{uuid_pkg.uuid4()}/ai-prediction"
    res = await client.post(url)
    assert res.status_code == 404


async def test_run_prediction_without_xray_returns_422(client, db_session):
    from app.models.medical_record import MedicalRecord
    from app.models.patient import Patient

    patient = Patient(
        uuid=str(uuid_pkg.uuid4()), name="무X레이", age=30,
        gender="female", phone="01099998888",
    )
    db_session.add(patient)
    await db_session.flush()
    record = MedicalRecord(
        uuid=str(uuid_pkg.uuid4()), patient_id=patient.uuid,
        chart_number="CHART-NOXRAY", symptoms="두통",
    )
    db_session.add(record)
    await db_session.commit()

    url = f"/api/v1/patients/{patient.uuid}/medical-records/{record.uuid}/ai-prediction"
    res = await client.post(url)
    assert res.status_code == 422


async def test_list_predictions(client, seeded_record):
    base = f"/api/v1/patients/{seeded_record['patient_id']}"
    await client.post(
        f"{base}/medical-records/{seeded_record['record_id']}/ai-prediction"
    )

    res = await client.get(f"{base}/ai-predictions")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["page"] == 1 and data["size"] == 20 and data["total_pages"] == 1
    item = data["items"][0]
    assert item["chart_number"] == "CHART-TEST-001"
    assert item["is_pneumonia"] is True
    assert "from_cache" not in item
    assert "label" not in item


async def test_list_predictions_patient_not_found(client):
    res = await client.get(f"/api/v1/patients/{uuid_pkg.uuid4()}/ai-predictions")
    assert res.status_code == 404


async def test_list_predictions_empty(client, seeded_record):
    res = await client.get(
        f"/api/v1/patients/{seeded_record['patient_id']}/ai-predictions"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 0
