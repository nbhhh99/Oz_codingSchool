# 6일차 - 폐렴 예측 API 설계서

## 개요

진료기록에 등록된 흉부 X-Ray 이미지를 `worker/model.py`의 SimpleCNN 모델로 분석하여 폐렴 여부를 예측하는 API. 동일한 진료기록에 대해 같은 모델로 이미 예측한 결과가 있으면 재추론 없이 저장된 결과를 그대로 반환한다.

관련 요구사항: REQ-PRED-001(AI 모델 활용 폐렴 예측), REQ-PRED-002(AI 모델 활용 폐렴 예측 결과 조회), NFR-PRED-001(모델 평가 기준), NFR-PRED-002(API 성능, 3초 이내 응답)

사용 모델 및 저장 테이블: `worker/model.py`의 `predict()` 결과를 `ai_analysis_results` 테이블(3일차에 정의된 `AiAnalysisResult` 모델)에 저장한다.

### 모델 평가 기준 (NFR-PRED-001)

| 지표 | 정의 | 계산식 | 목표치 |
|---|---|---|---|
| Recall(민감도) | 실제 폐렴 환자를 얼마나 놓치지 않는가 | TP / (TP + FN) | 0.90 ~ 0.95 (최소 0.90) |
| Accuracy | 전체 예측 정확도 (보조 지표) | (TP + TN) / 전체 표본 수 | 0.80 ~ 0.90 |

FN(폐렴 환자를 정상으로 오진)이 가장 위험한 오류 유형이므로, Recall을 Accuracy보다 우선 지표로 본다. 이 수치는 API 자체의 응답 스펙은 아니지만, 1단계에서 검증한 모델 성능이 이 기준을 충족하는지 확인하는 근거 자료로 설계서에 함께 기록한다.

## 엔드포인트 목록

| Method | URL | 설명 | 대응 요구사항|
|---|---|---|---|
| POST | `/api/v1/medical-records/{record_id}/ai-prediction` | 폐렴 예측 실행 또는 캐시된 결과 조회 | REQ-PRED-001 |
| GET | `/api/v1/patients/{patient_id}/ai-predictions` | 환자별 예측 결과 목록 조회 | REQ-PRED-002 |

## 1. POST /api/v1/medical-records/{record_id}/ai-prediction

진료기록 상세 페이지에서 "AI 예측 결과보기" 버튼 클릭 시 호출한다. 요청 시점의 처리 흐름은 다음과 같다.

1. `record_id`에 해당하는 진료기록이 존재하는지 확인 (없으면 404)
2. 해당 진료기록에 첨부된 X-Ray 이미지가 있는지 확인 (없으면 422)
3. 같은 `record_id` + 같은 `ai_model`(모델 버전) 조합으로 이미 저장된 `AiAnalysisResult`가 있는지 조회
   - 있으면: AI 추론을 다시 실행하지 않고 저장된 결과를 그대로 응답 (200)
   - 없으면: `worker/model.py`의 `predict()`를 호출해 새로 추론하고, 결과를 저장한 뒤 응답 (201)

### Path Parameters

| 이름 | 타입 | 설명 |
|---|---|---|
| record_id | UUID | 진료기록 고유 ID |

### Response Body (200 / 201 공통)

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "medical_record_id": "e5a1c2b0-...",
  "is_pneumonia": true,
  "label": "PNEUMONIA",
  "confidence": 94.32,
  "heatmap_image_url": null,
  "ai_model": "simple_cnn_v1",
  "predicted_at": "2026-08-31T10:20:00Z",
  "from_cache": false
}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 예측 결과 고유 ID |
| medical_record_id | UUID | 대상 진료기록 ID |
| is_pneumonia | boolean | 폐렴 여부 |
| label | string | `"NORMAL"` 또는 `"PNEUMONIA"` |
| confidence | float | 예측 클래스에 대한 확신도 (%, 0~100) |
| heatmap_image_url | string \| null | 히트맵 이미지 경로 (선택 사항, 미구현 시 null) |
| ai_model | string | 예측에 사용한 모델 식별자/버전 |
| predicted_at | datetime | 예측 수행 일시 (캐시 응답인 경우 최초 예측 시각) |
| from_cache | boolean | 기존 저장 결과를 그대로 반환했는지 여부 |

### 에러 응답

| 상태 코드 | 상황 |
|---|---|
| 404 | `record_id`에 해당하는 진료기록 없음 |
| 422 | 진료기록에 X-Ray 이미지가 첨부되어 있지 않음 |
| 500 | 모델 추론 중 오류 발생 |

## 2. GET /api/v1/patients/{patient_id}/ai-predictions

환자 상세 페이지의 "AI 예측 결과" 섹션에서 사용한다. 해당 환자의 모든 진료기록에 대한 예측 결과를 최신순으로 목록 조회한다.

### Path Parameters

| 이름 | 타입 | 설명 |
|---|---|---|
| patient_id | UUID | 환자 고유 ID |

### Query Parameters

| 이름 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| page | int | 1 | 페이지 번호 |
| size | int | 20 | 페이지당 항목 수 |

### Response Body

```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "medical_record_id": "e5a1c2b0-...",
      "chart_number": "CN-2026-0031",
      "is_pneumonia": true,
      "confidence": 94.32,
      "heatmap_image_url": null,
      "ai_model": "simple_cnn_v1",
      "predicted_at": "2026-08-31T10:20:00Z"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

목록 항목의 필드는 REQ-PRED-002에서 요구한 "고유 ID, 폐렴 여부, Confidence, Heatmap Image URL, 예측 수행 일시, 사용한 모델"에 `chart_number`(어느 진료기록에 대한 예측인지 식별용)를 추가한 구성이다.

### 에러 응답

| 상태 코드 | 상황 |
|---|---|
| 404 | `patient_id`에 해당하는 환자 없음 |

## 확인 필요 사항 (1단계 PR 리뷰에서 이월된 항목)

1. **정규화 값**: `worker/model.py`의 전처리가 학습 시 사용한 `Normalize` 값과 일치하는지 모델 학습 담당자 확인 필요. 확률(`confidence`) 값의 정확도에 직접 영향.
2. **클래스 순서**: `0=NORMAL, 1=PNEUMONIA` 가정이 실제 학습 라벨과 일치하는지 확인 필요. 틀릴 경우 `is_pneumonia`/`label` 값이 반대로 응답됨.
3. **worker 의존성 구조**: `worker/model.py`를 API 서버 프로세스에서 직접 import할지, 별도 프로세스로 분리할지 결정 필요. 직접 import한다면 API 서버의 `pyproject.toml`에도 `torch`, `torchvision`을 의존성으로 추가해야 함.