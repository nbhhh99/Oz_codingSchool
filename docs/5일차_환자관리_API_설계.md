# 환자 관리 및 진료기록 API 설계

## 1. 문서 개요

- 목적: 환자 정보와 흉부 X-Ray 진료기록의 등록·조회·수정·삭제 API 계약 정의
- Base URL: `/api/v1`
- 일반 데이터 형식: `application/json`
- 이미지 업로드 형식: `multipart/form-data`
- 리소스 ID: UUID
- 인증 방식: `Authorization: Bearer {access_token}`
- 대상 요구사항: `REQ-PTNT-001~005`, `REQ-MDR-001~003`, `NFR-PTNT-001`, `NFR-MDR-001`

> 이 문서는 API 명세를 정의한다. 모달, 버튼, 이미지 미리보기, 증상 100자 말줄임 표시는 프런트엔드에서 구현한다.

---

## 2. 공통 정책

### 2.1 Enum

| 구분 | API 값 | 의미 |
|---|---|---|
| 성별 | `male` | 남성 |
| 성별 | `female` | 여성 |
| 부서 | `MEDICAL` | 의료 실무진 |
| 부서 | `DEV` | 개발진 |
| 부서 | `RESEARCH` | 연구진 |
| 권한 | `STAFF` | 업무 데이터 접근 가능 |
| 권한 | `ADMIN` | 전체 데이터 접근 가능 |

환자 성별 값은 현재 `Patient` 모델의 Enum인 `male`, `female`을 사용한다.

### 2.2 인증 및 인가

| 작업 | 접근 조건 |
|---|---|
| 환자 등록 | 활성 사용자이며 `department=MEDICAL`, `role=STAFF` 또는 `ADMIN` |
| 진료기록 등록 | 활성 사용자이며 `department=MEDICAL`, `role=STAFF` 또는 `ADMIN` |
| 환자·진료기록 조회 | 활성 사용자이며 `role=STAFF` 또는 `ADMIN` |
| 환자 수정·삭제 | 활성 사용자이며 `role=STAFF` 또는 `ADMIN` |

- 인증 토큰 누락·만료·위변조: `401 Unauthorized`
- 로그인했지만 권한 또는 부서 조건 불충족: `403 Forbidden`
- `PENDING` 또는 `is_active=false` 계정은 모든 보호 API 접근을 거부한다.

### 2.3 입력 검증

| 필드 | 규칙 |
|---|---|
| `name` | 필수, 앞뒤 공백 제거, 1~30자 |
| `age` | 필수, 정수, 0~150 |
| `gender` | 필수, `male` 또는 `female` |
| `phone` | 필수, 숫자 11자리(`01012345678`), 하이픈 입력 시 제거 후 저장 |
| `chart_number` | 필수, 앞뒤 공백 제거, 1~50자, 전체 시스템에서 유일 |
| `symptoms` | 필수, 공백만 입력 불가 |
| `xray_image` | 필수, JPEG 또는 PNG, 최대 10MB |

휴대폰 번호의 중복 허용 여부는 요구사항에 명시되지 않았으므로 이 명세에서는 중복을 제한하지 않는다.

### 2.4 페이지네이션과 정렬

- 목록 API는 `page` 기본값 1, `size` 기본값 20을 사용한다.
- `size`는 1~100 범위로 제한한다.
- 기본 정렬은 `created_at` 내림차순이다.
- 검색·필터 결과가 없으면 빈 `items` 배열과 `200 OK`를 반환한다.

---

## 3. API 목록

| 요구사항 ID | Method | Endpoint | 기능 | 권한 |
|---|---|---|---|---|
| REQ-PTNT-001 | POST | `/patients` | 환자 등록 | 의료인 |
| REQ-PTNT-002 | GET | `/patients` | 환자 목록·검색·필터 | STAFF, ADMIN |
| REQ-PTNT-003 | GET | `/patients/{patient_id}` | 환자 상세 조회 | STAFF, ADMIN |
| REQ-PTNT-004 | PATCH | `/patients/{patient_id}` | 환자 이름·연락처 수정 | STAFF, ADMIN |
| REQ-PTNT-005 | DELETE | `/patients/{patient_id}` | 환자 및 관련 데이터 영구 삭제 | STAFF, ADMIN |
| REQ-MDR-001 | POST | `/patients/{patient_id}/medical-records` | 진료기록·X-Ray 등록 | 의료인 |
| REQ-MDR-002 | GET | `/patients/{patient_id}/medical-records` | 환자별 진료기록 목록 | STAFF, ADMIN |
| REQ-MDR-003 | GET | `/patients/{patient_id}/medical-records/{record_id}` | 진료기록 상세 조회 | STAFF, ADMIN |

---

## 4. 환자 API 상세 명세

### 4.1 환자 등록

**POST `/api/v1/patients`**

요청:

```json
{
  "name": "김환자",
  "age": 45,
  "gender": "female",
  "phone": "01012345678"
}
```

성공 응답 — `201 Created`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "김환자",
  "age": 45,
  "gender": "female",
  "phone": "01012345678",
  "created_at": "2026-08-28T10:00:00Z",
  "updated_at": "2026-08-28T10:00:00Z"
}
```

- 입력 검증 실패: `422 Unprocessable Entity`
- 의료인 조건 불충족: `403 Forbidden`

### 4.2 환자 목록 조회

**GET `/api/v1/patients`**

| Query Parameter | 타입 | 필수 | 기본값 | 설명 |
|---|---|:---:|---|---|
| `search` | string | X | - | 이름 부분 검색 |
| `gender` | enum | X | - | `male`, `female` |
| `min_age` | integer | X | - | 최소 나이, 0~150 |
| `max_age` | integer | X | - | 최대 나이, 0~150 |
| `page` | integer | X | 1 | 페이지 번호 |
| `size` | integer | X | 20 | 페이지 크기, 1~100 |

- 검색어, 성별, 나이 범위 필터는 함께 사용할 수 있다.
- `min_age`가 `max_age`보다 크면 `422 Unprocessable Entity`를 반환한다.

성공 응답 — `200 OK`:

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "김환자",
      "age": 45,
      "gender": "female",
      "phone": "01012345678",
      "created_at": "2026-08-28T10:00:00Z",
      "updated_at": "2026-08-28T10:00:00Z"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

### 4.3 환자 상세 조회

**GET `/api/v1/patients/{patient_id}`**

성공 응답 — `200 OK`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "김환자",
  "age": 45,
  "gender": "female",
  "phone": "01012345678"
}
```

- UUID 형식 오류: `422 Unprocessable Entity`
- 환자 없음: `404 Not Found`

### 4.4 환자 정보 수정

**PATCH `/api/v1/patients/{patient_id}`**

Partial Update이므로 변경할 필드만 전송한다. 수정 가능한 필드는 `name`, `phone`뿐이다.

요청 예시:

```json
{
  "name": "김수정",
  "phone": "01098765432"
}
```

성공 응답 — `200 OK`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "김수정",
  "age": 45,
  "gender": "female",
  "phone": "01098765432",
  "created_at": "2026-08-28T10:00:00Z",
  "updated_at": "2026-08-28T11:00:00Z"
}
```

- 빈 요청 또는 수정 불가 필드 포함: `422 Unprocessable Entity`
- 환자 없음: `404 Not Found`

### 4.5 환자 정보 삭제

**DELETE `/api/v1/patients/{patient_id}`**

- 요청 본문 없음
- 성공 응답: `204 No Content`
- 삭제 확인 모달과 `확인했습니다` 체크는 프런트엔드 책임이며, 확인 완료 후 이 API를 호출한다.
- 하나의 삭제 작업에서 환자, 해당 환자의 모든 진료기록, AI 분석 결과, X-Ray 이미지 DB 행을 영구 삭제한다.
- DB 관계는 명시적인 삭제 순서 또는 `delete-orphan`/`ON DELETE CASCADE`로 처리한다.
- X-Ray의 로컬 실제 파일도 삭제한다. DB 트랜잭션 실패 시 파일만 먼저 사라지지 않도록 삭제 대상 경로를 수집하고 DB 반영 성공 후 파일 삭제를 완료하며, 파일 삭제 실패는 기록하고 재처리한다.
- 저장된 DB 경로만 사용하고 정규화된 경로가 지정된 `media` 디렉터리 내부인지 검증하여 경로 조작을 방지한다.
- 환자 없음: `404 Not Found`

---

## 5. 진료기록 API 상세 명세

### 5.1 진료기록 등록

**POST `/api/v1/patients/{patient_id}/medical-records`**

Content-Type: `multipart/form-data`

| Form 필드 | 타입 | 필수 | 설명 |
|---|---|:---:|---|
| `chart_number` | string | O | 진료 차트 넘버, 전체 시스템에서 유일 |
| `symptoms` | string | O | 진료된 증상 |
| `xray_image` | file | O | JPEG 또는 PNG 흉부 X-Ray 이미지 |
| `shooting_datetime` | datetime | X | 촬영일시, 미입력 시 서버 수신 시각 |

환자 고유 ID는 URL의 `patient_id`로 전달하므로 본문에 중복 전송하지 않는다. 프런트엔드는 업로드된 로컬 파일을 `URL.createObjectURL()` 또는 `FileReader`로 미리보기 한 뒤 제출한다.

성공 응답 — `201 Created`:

```json
{
  "id": "650e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "chart_number": "CHART-20260828-001",
  "symptoms": "기침과 발열이 지속됨",
  "xray_image": {
    "id": "750e8400-e29b-41d4-a716-446655440002",
    "url": "/media/xrays/2026/08/28/750e8400-e29b-41d4-a716-446655440002.jpg",
    "shooting_datetime": "2026-08-28T09:30:00Z"
  },
  "created_at": "2026-08-28T10:00:00Z"
}
```

파일 저장 정책:

- 서버 실행 환경의 `{BASE_DIR}/media/xrays/YYYY/MM/DD/` 아래에 저장한다.
- 사용자가 보낸 파일명은 저장 파일명으로 사용하지 않고 서버가 생성한 UUID를 사용한다.
- 파일 시그니처와 확장자를 함께 검사하고, 허용 형식만 저장한다.
- DB에는 로컬 절대경로 대신 `/media/...` 상대 URL을 저장한다.
- DB 저장 실패 시 생성한 파일을 제거하여 고아 파일을 남기지 않는다.

오류:

- 환자 없음: `404 Not Found`
- 차트 넘버 중복: `409 Conflict`
- 이미지 형식·크기 또는 입력 검증 실패: `422 Unprocessable Entity`
- 파일 저장 실패: `500 Internal Server Error`

### 5.2 진료기록 목록 조회

**GET `/api/v1/patients/{patient_id}/medical-records`**

| Query Parameter | 타입 | 필수 | 기본값 | 설명 |
|---|---|:---:|---|---|
| `page` | integer | X | 1 | 페이지 번호 |
| `size` | integer | X | 20 | 페이지 크기, 1~100 |

성공 응답 — `200 OK`:

```json
{
  "items": [
    {
      "id": "650e8400-e29b-41d4-a716-446655440001",
      "chart_number": "CHART-20260828-001",
      "symptoms": "기침과 발열이 지속됨",
      "created_at": "2026-08-28T10:00:00Z"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

- API는 증상 원문을 반환한다.
- 목록 화면은 증상이 100자를 초과하면 앞 100자 뒤에 `…`를 붙여 표시한다.
- 환자 없음: `404 Not Found`

### 5.3 진료기록 상세 조회

**GET `/api/v1/patients/{patient_id}/medical-records/{record_id}`**

성공 응답 — `200 OK`:

```json
{
  "id": "650e8400-e29b-41d4-a716-446655440001",
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "chart_number": "CHART-20260828-001",
  "symptoms": "기침과 발열이 지속됨",
  "xray_images": [
    {
      "id": "750e8400-e29b-41d4-a716-446655440002",
      "url": "/media/xrays/2026/08/28/750e8400-e29b-41d4-a716-446655440002.jpg",
      "shooting_datetime": "2026-08-28T09:30:00Z",
      "created_at": "2026-08-28T10:00:00Z"
    }
  ],
  "created_at": "2026-08-28T10:00:00Z"
}
```

- 환자 없음: `404 Not Found`
- 진료기록이 없거나 해당 환자 소유가 아님: `404 Not Found`

---

## 6. 공통 오류 응답

```json
{
  "detail": {
    "code": "PATIENT_NOT_FOUND",
    "message": "환자를 찾을 수 없습니다."
  }
}
```

| HTTP 상태 | 사용 기준 |
|---|---|
| `401 Unauthorized` | 토큰 누락·만료·위변조 |
| `403 Forbidden` | 계정 비활성, 역할 또는 부서 권한 부족 |
| `404 Not Found` | 환자 또는 진료기록 없음 |
| `409 Conflict` | 진료 차트 넘버 중복 등 현재 상태와 충돌 |
| `422 Unprocessable Entity` | 형식, 범위, Enum, 필수값, 파일 검증 실패 |
| `500 Internal Server Error` | 예상하지 못한 DB·파일 저장 오류 |

운영 오류 응답에는 DB 쿼리, 로컬 절대경로, 스택 트레이스 등 내부 정보를 포함하지 않는다.

## 7. 비기능 요구사항 반영

### NFR-PTNT-001 / NFR-MDR-001 API 성능

- 모든 환자·진료기록 API는 정상 운영 조건에서 요청 수신 후 3초 이내 응답을 목표로 한다.
- 환자 및 진료기록 목록에 페이지네이션을 적용한다.
- `patients.name`, `patients.gender`, `patients.age`, `medical_records.patient_id`, `medical_records.created_at`, `medical_records.chart_number` 인덱스를 검토한다.
- 목록 조회는 필요한 컬럼만 선택하고 N+1 쿼리를 방지한다.
- 이미지 파일 자체는 목록 응답에 포함하지 않고 상세 응답에서도 URL만 반환한다.
- 업로드 크기를 10MB로 제한하고 파일 저장 시간을 포함하여 처리시간을 측정한다.
- API별 처리시간을 모니터링하고 3초 초과 요청을 기록한다.

## 8. 데이터 무결성 및 보안

- 환자 및 진료기록 작업은 서버에서 매 요청마다 최신 사용자 권한을 확인한다.
- 환자 삭제와 관련 DB 삭제는 하나의 트랜잭션으로 처리한다.
- 진료기록 생성과 X-Ray DB 행 생성도 하나의 트랜잭션으로 처리한다.
- 업로드 파일명, MIME 타입만 신뢰하지 않고 파일 시그니처를 검사한다.
- 환자 연락처와 진료정보는 로그에 원문으로 기록하지 않는다.
- 파일 경로를 API 입력으로 받지 않으며, 다운로드·삭제 시 허용된 `media` 경로 이탈을 차단한다.

## 9. 요구사항 추적표

| 요구사항 ID | 반영 API·설계 |
|---|---|
| REQ-PTNT-001 | `POST /patients` |
| REQ-PTNT-002 | `GET /patients`, 이름 검색·성별·나이 필터·페이지네이션 |
| REQ-PTNT-003 | `GET /patients/{patient_id}` |
| REQ-PTNT-004 | `PATCH /patients/{patient_id}`, 이름·연락처만 수정 |
| REQ-PTNT-005 | `DELETE /patients/{patient_id}`, 연관 DB·로컬 파일 영구 삭제 |
| REQ-MDR-001 | `POST /patients/{patient_id}/medical-records`, multipart 이미지 업로드 |
| REQ-MDR-002 | `GET /patients/{patient_id}/medical-records`, 100자 말줄임 UI 정책 |
| REQ-MDR-003 | `GET /patients/{patient_id}/medical-records/{record_id}` |
| NFR-PTNT-001 | 3초 성능 목표, 페이지네이션·인덱스·모니터링 |
| NFR-MDR-001 | 3초 성능 목표, 이미지 크기 제한·URL 응답·모니터링 |
