# 폐렴 예측 API 설계

## 1. 문서 개요

- 목적: 진료기록에 등록된 흉부 X-Ray 이미지를 AI 모델로 분석해 폐렴 여부를 예측·조회하는 API 계약 정의
- Base URL: `/api/v1`
- 일반 데이터 형식: `application/json`
- 리소스 ID: UUID
- 인증 방식: `Authorization: Bearer {access_token}`
- 대상 요구사항: `REQ-PRED-001~002`, `NFR-PRED-001~002`
- 사용 모델: `worker/model.py`(PR #18, 병합 완료)의 SimpleCNN

> 이 문서는 API 명세를 정의한다. 히트맵 이미지 생성 자체는 이번 단계 범위 밖이며, `heatmap_image_url`은 필드만 예약해 둔다.

---

## 2. 공통 정책

### 2.1 모델 식별자

`ai_model` 값은 `worker/model.py`에 정의된 상수를 그대로 사용한다.

```python
AI_MODEL_NAME = "SimpleCNN"   # DB(ai_analysis_results.ai_model)에 기록할 모델 식별자
```

캐시 조회(`record_id` + `ai_model` 조합)가 이 문자열에 의존하므로, API 응답과 DB 저장값 모두 `"SimpleCNN"`으로 고정한다.

### 2.2 인증 및 인가

| 작업 | 접근 조건 |
|---|---|
| AI 예측 실행/조회 | 활성 사용자이며 `role=STAFF` 또는 `ADMIN` (부서 무관) |
| AI 예측 결과 목록 조회 | 활성 사용자이며 `role=STAFF` 또는 `ADMIN` (부서 무관) |

- 요구사항이 접근 주체를 "사내 의료인, 개발팀, 연구자 권한"으로 정의해 특정 부서로 제한하지 않으므로, 부서 조건 없이 역할만 검사하는 기존 `get_current_staff`를 재사용한다. 부서를 `MEDICAL`로 제한하는 `get_current_medical_staff`는 사용하지 않는다.
- 인증 토큰 누락·만료·위변조: `401 Unauthorized`
- 로그인했지만 권한 조건 불충족: `403 Forbidden`
- `PENDING` 또는 `is_active=false` 계정은 모든 보호 API 접근을 거부한다.

### 2.3 입력 검증

| 필드 | 규칙 |
|---|---|
| `patient_id` | 필수, UUID 형식, 해당 환자 존재해야 함 |
| `record_id` | 필수, UUID 형식, `patient_id` 소유의 진료기록이어야 함 |

- 대상 진료기록에 X-Ray 이미지가 한 장도 없으면 예측을 실행할 수 없다.
- 진료기록에 X-Ray 이미지가 여러 장 등록되어 있으면(`xray_images.record_id`는 unique 아님), `shooting_datetime`이 가장 최신인 이미지 1장만 추론 대상으로 삼는다.

### 2.4 페이지네이션과 정렬

- 목록 API는 `page` 기본값 1, `size` 기본값 20을 사용한다.
- `size`는 1~100 범위로 제한한다.
- 정렬은 `predicted_at`(=`created_at`) 내림차순(최신순)으로 고정하며, 별도 정렬 옵션은 제공하지 않는다.
- 검색 결과가 없으면 빈 `items` 배열과 `200 OK`를 반환한다.

---

## 3. API 목록

| 요구사항 ID | Method | Endpoint | 기능 | 권한 |
|---|---|---|---|---|
| REQ-PRED-001 | POST | `/patients/{patient_id}/medical-records/{record_id}/ai-prediction` | 폐렴 예측 실행 또는 캐시 조회 | STAFF, ADMIN |
| REQ-PRED-002 | GET | `/patients/{patient_id}/ai-predictions` | 환자별 예측 결과 목록 조회 | STAFF, ADMIN |

기존 저장소 컨벤션(`patient_apis.py`, `medical_record_apis.py`)이 전부 `/patients/{patient_id}/...`로 중첩되어 있으므로, 두 엔드포인트 모두 환자 하위로 중첩해 통일한다.

---

## 4. AI 예측 API 상세 명세

### 4.1 폐렴 예측 실행/조회

**POST `/api/v1/patients/{patient_id}/medical-records/{record_id}/ai-prediction`**

처리 흐름:

1. `patient_id`에 해당 환자가 존재하는지, `record_id`가 그 환자 소유의 진료기록인지 확인
2. 해당 진료기록에 첨부된 X-Ray 이미지가 있는지 확인 (2.3의 다중 이미지 규칙 적용)
3. `record_id` + `ai_model="SimpleCNN"` 조합으로 이미 저장된 `AiAnalysisResult`가 있는지 조회
   - 있으면: AI 추론을 다시 실행하지 않고 저장된 결과를 그대로 응답 (`200 OK`)
   - 없으면: `worker/model.py`의 `predict()`를 호출해 새로 추론하고 결과를 저장한 뒤 응답 (`201 Created`)

요청 본문 없음 (경로 파라미터만 사용).

성공 응답 — `200 OK` / `201 Created` 공통:

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "medical_record_id": "650e8400-e29b-41d4-a716-446655440001",
  "is_pneumonia": true,
  "label": "PNEUMONIA",
  "confidence": 94.32,
  "heatmap_image_url": null,
  "ai_model": "SimpleCNN",
  "predicted_at": "2026-08-31T10:20:00Z",
  "from_cache": false
}
```

오류:

- 환자 없음: `404 Not Found`
- 진료기록이 없거나 해당 환자 소유가 아님: `404 Not Found`
- 진료기록에 X-Ray 이미지가 첨부되어 있지 않음: `422 Unprocessable Entity`
- 모델 추론 중 오류: `500 Internal Server Error`

### 4.2 폐렴 예측 결과 목록 조회

**GET `/api/v1/patients/{patient_id}/ai-predictions`**

| Query Parameter | 타입 | 필수 | 기본값 | 설명 |
|---|---|:---:|---|---|
| `page` | integer | X | 1 | 페이지 번호 |
| `size` | integer | X | 20 | 페이지 크기, 1~100 |

성공 응답 — `200 OK`:

```json
{
  "items": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "medical_record_id": "650e8400-e29b-41d4-a716-446655440001",
      "chart_number": "CHART-20260828-001",
      "is_pneumonia": true,
      "confidence": 94.32,
      "heatmap_image_url": null,
      "ai_model": "SimpleCNN",
      "predicted_at": "2026-08-31T10:20:00Z"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

오류:

- 환자 없음: `404 Not Found`

### 4.3 API 필드 ↔ DB 컬럼 매핑

| API 필드 | DB 컬럼(`ai_analysis_results`) | 비고 |
|---|---|---|
| `id` | `uuid` | PK |
| `medical_record_id` | `record_id` | 컬럼명과 다르므로 응답 시리얼라이저에서 매핑 |
| `is_pneumonia` | `is_pneumonia` | 동일 |
| `label` | (컬럼 없음) | `is_pneumonia`를 `"PNEUMONIA"`/`"NORMAL"` 문자열로 변환한 파생 필드 |
| `confidence` | `confidence` | `DECIMAL(5,2)` → 응답 시 `float` 변환 |
| `heatmap_image_url` | `heatmap_url` | 컬럼명과 다르므로 매핑. nullable 이슈는 7장 참고 |
| `ai_model` | `ai_model` | `"SimpleCNN"` 고정 |
| `predicted_at` | `created_at` | `TimestampMixin`의 `created_at`을 그대로 사용, API 필드명만 변경 |

---

## 5. 공통 오류 응답

```json
{
  "detail": {
    "code": "MEDICAL_RECORD_NOT_FOUND",
    "message": "진료기록을 찾을 수 없습니다."
  }
}
```

| HTTP 상태 | 사용 기준 |
|---|---|
| `401 Unauthorized` | 토큰 누락·만료·위변조 |
| `403 Forbidden` | 계정 비활성 또는 역할 권한 부족 |
| `404 Not Found` | 환자 또는 진료기록 없음 |
| `422 Unprocessable Entity` | 진료기록에 X-Ray 이미지 없음 등 검증 실패 |
| `500 Internal Server Error` | 모델 추론, DB 저장 등 예상하지 못한 오류 |

운영 오류 응답에는 DB 쿼리, 로컬 절대경로, 스택 트레이스 등 내부 정보를 포함하지 않는다.

---

## 6. 비기능 요구사항 반영

### NFR-PRED-001 모델 평가 기준

| 지표 | 정의 | 계산식 | 목표치 |
|---|---|---|---|
| Recall(민감도) | 실제 폐렴 환자를 얼마나 놓치지 않는가 | TP / (TP + FN) | 0.90 ~ 0.95 (최소 0.90) |
| Accuracy | 전체 예측 정확도 (보조 지표) | (TP + TN) / 전체 표본 수 | 0.80 ~ 0.90 |

FN(폐렴 환자를 정상으로 오진)이 가장 위험한 오류 유형이므로, Recall을 Accuracy보다 우선 지표로 본다.

### NFR-PRED-002 API 성능 (3초 이내 응답)

- SimpleCNN 추론은 CPU-bound 동기 연산이므로, FastAPI 이벤트 루프를 막지 않도록 핸들러는 동기 `def`로 선언하거나 `run_in_threadpool`로 감싸 스레드풀에서 실행한다. 별도 메시지 큐·백그라운드 워커 도입은 이번 단계 범위 밖이다.
- 캐시 조회(`record_id` + `ai_model`)를 추론 실행보다 먼저 수행해, 캐시 히트 시에는 모델 로딩·추론 자체를 생략한다.
- `worker/model.py` 담당자가 로컬 CPU 환경에서 측정한 1회 추론 평균 처리 시간을 기록한다. (TODO: 실측치 채워 넣기)
- `ai_analysis_results(record_id, ai_model)` 복합 인덱스를 추가한다. 캐시 조회 쿼리가 이 두 컬럼으로 필터링하므로, 인덱스 없이는 데이터가 쌓일수록 응답 시간이 3초 기준을 초과할 수 있다.
- 처리 시간을 API별로 측정하고, 3초를 초과하는 요청은 경고 로그로 기록한다. 반복 발생 시 비동기 큐 도입을 재검토한다.

---

## 7. 데이터 무결성 및 보안

- AI 예측 작업은 서버에서 매 요청마다 최신 사용자 권한을 확인한다.
- `heatmap_url` 컬럼은 현재 `nullable=False`이나, 요구사항은 Heatmap Image URL을 선택 사항으로 정의한다. 히트맵 생성 기능이 이번 단계 범위 밖이므로 `nullable=True`로 변경하는 마이그레이션을 이번 PR 또는 후속 PR에서 함께 진행한다.
- `ai_model` 값은 상수(`AI_MODEL_NAME`)로 고정해 캐시 키 불일치를 방지한다.
- 모델 추론 결과와 신뢰도(`confidence`) 값은 로그에 환자 식별 정보와 함께 원문으로 기록하지 않는다.

---

## 8. 확인 필요 사항 (worker 1단계 PR에서 이월)

1. **정규화 값**: `worker/model.py`의 전처리가 학습 시 사용한 `Normalize` 값과 일치하는지 모델 학습 담당자 확인 필요.
2. **클래스 순서**: `0=NORMAL, 1=PNEUMONIA` 가정이 실제 학습 라벨과 일치하는지 확인 필요.
3. **worker 의존성 구조**: `worker/model.py`를 API 서버 프로세스에서 직접 import할지, 별도 프로세스로 분리할지 결정 필요. 직접 import한다면 API 서버의 `pyproject.toml`에도 `torch`, `torchvision`을 의존성으로 추가해야 함.

---

## 9. 요구사항 추적표

| 요구사항 ID | 반영 API·설계 |
|---|---|
| REQ-PRED-001 | `POST /patients/{patient_id}/medical-records/{record_id}/ai-prediction`, 캐시 조회 후 추론 |
| REQ-PRED-002 | `GET /patients/{patient_id}/ai-predictions`, 최신순 페이지네이션 |
| NFR-PRED-001 | 6장 모델 평가 기준(Recall/Accuracy 목표치) |
| NFR-PRED-002 | 6장 API 성능(동기 처리, 캐시 히트 시 추론 생략, 인덱스, 로깅) |