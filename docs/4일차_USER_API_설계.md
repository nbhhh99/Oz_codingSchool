# User API 설계

## 1. 문서 개요

- 목적: User 도메인의 회원가입, 인증·인가, 회원 관리, 마이페이지 API 명세
- Base URL: `/api/v1`
- 데이터 형식: `application/json`
- 사용자 ID: UUID
- 인증 방식: JWT Bearer Access Token + HttpOnly Refresh Token 쿠키
- 대상 요구사항: `REQ-USER-001~009`, `NFR-USER-001~003`

> 이 문서는 API 계약을 정의한다. 비밀번호 마스킹과 보기 아이콘은 프런트엔드에서 `NFR-USER-002`에 따라 구현한다.

---

## 2. 공통 Enum

| 구분 | API 값 | 의미 |
|---|---|---|
| 부서 | `RESEARCH` | 연구 |
| 부서 | `MEDICAL` | 의료 |
| 부서 | `DEV` | 개발 |
| 성별 | `M` | 남성 |
| 성별 | `F` | 여성 |
| 권한 | `PENDING` | 대기자 |
| 권한 | `STAFF` | 스태프 |
| 권한 | `ADMIN` | 어드민 |

신규 회원의 기본 권한은 `PENDING`, 계정 활성화 여부는 `true`로 생성한다.

## 3. 인증 및 인가 정책

### 3.1 토큰 정책

| 항목 | 정책 |
|---|---|
| Access Token | 만료 30분, 응답 본문으로 전달 |
| Refresh Token | 만료 7일, `HttpOnly` 쿠키로 전달 |
| JWT Payload | 최소 식별 정보인 `user_id`만 저장 |
| Access Token 사용 | `Authorization: Bearer {access_token}` |
| Refresh Cookie 권장 속성 | `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` |
| Access Token 만료 | Refresh API를 호출해 재발급 |
| Refresh Token 만료·무효 | `401 Unauthorized`, 재로그인 유도 |

서버는 Refresh Token 원문 대신 해시 또는 토큰 식별자를 저장하여 폐기 여부를 관리한다. 로그아웃, 비밀번호 변경, 회원 탈퇴 시 해당 사용자의 Refresh Token을 폐기한다.

### 3.2 권한별 접근 범위

| 기능 | PENDING | STAFF | ADMIN |
|---|:---:|:---:|:---:|
| 마이페이지 조회·수정 | O | O | O |
| 비밀번호 변경·회원 탈퇴·로그아웃 | O | O | O |
| 흉부 X-Ray 관련 읽기·쓰기·수정 | X | O | O |
| 전체 회원 목록 조회 | X | X | O |
| 회원 권한 변경 | X | X | O |
| 시스템 전체 데이터 접근 | X | X | O |

- 비로그인 또는 유효하지 않은 토큰: `401 Unauthorized`
- 권한 부족: `403 Forbidden`
- `is_active=false` 계정: 로그인 및 보호 API 접근 거부

---

## 4. API 목록

| 요구사항 ID | Method | Endpoint | 기능 | 인증·권한 |
|---|---|---|---|---|
| REQ-USER-001 | POST | `/auth/signup` | 회원가입 | 불필요 |
| REQ-USER-002 | POST | `/auth/login` | 로그인 | 불필요 |
| NFR-USER-001 | POST | `/auth/refresh` | Access Token 재발급 | Refresh 쿠키 |
| REQ-USER-003 | POST | `/auth/logout` | 로그아웃 | 로그인 사용자 |
| REQ-USER-004 | GET | `/admin/users` | 회원 목록·검색·필터 | ADMIN |
| REQ-USER-005 | PATCH | `/admin/users/{user_id}/role` | 회원 권한 변경 | ADMIN |
| REQ-USER-006 | GET | `/users/me` | 내 정보 조회 | 로그인 사용자 |
| REQ-USER-007 | PATCH | `/users/me` | 내 정보 일부 수정 | 로그인 사용자 |
| REQ-USER-008 | PATCH | `/users/me/password` | 비밀번호 변경 | 로그인 사용자 |
| REQ-USER-009 | DELETE | `/users/me` | 회원 탈퇴 | 로그인 사용자 |

---

## 5. 상세 API 명세

### 5.1 회원가입

**POST `/api/v1/auth/signup`**

요청:

```json
{
  "email": "staff@example.com",
  "password": "Password123!",
  "name": "홍길동",
  "department": "MEDICAL",
  "gender": "M",
  "phone_number": "010-1234-5678"
}
```

성공 응답 — `201 Created`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "staff@example.com",
  "name": "홍길동",
  "department": "MEDICAL",
  "gender": "M",
  "phone_number": "010-1234-5678",
  "role": "PENDING",
  "is_active": true
}
```

- 이메일 형식 오류 또는 필수값 누락: `422 Unprocessable Entity`
- 이메일 또는 휴대폰 번호 중복: `409 Conflict`
- 비밀번호는 해시 처리 후 저장하며 응답에 포함하지 않는다.

### 5.2 로그인

**POST `/api/v1/auth/login`**

요청:

```json
{
  "email": "staff@example.com",
  "password": "Password123!"
}
```

성공 응답 — `200 OK`:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

응답의 `Set-Cookie` 헤더로 Refresh Token을 전달한다.

- 이메일 또는 비밀번호 불일치: `401 Unauthorized`
- 비활성 계정: `403 Forbidden`
- 인증 실패 시 어느 항목이 틀렸는지 구분해 노출하지 않는다.

### 5.3 Access Token 재발급

**POST `/api/v1/auth/refresh`**

요청 본문은 없으며 브라우저가 HttpOnly Refresh Token 쿠키를 자동 전송한다.

성공 응답 — `200 OK`:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

- Refresh Token Rotation 적용 시 새 Refresh Token도 `Set-Cookie`로 교체한다.
- 쿠키 누락, 만료, 폐기 또는 위변조: `401 Unauthorized`

### 5.4 로그아웃

**POST `/api/v1/auth/logout`**

- 요청 본문 없음
- 서버에서 Refresh Token을 폐기하고 Refresh 쿠키를 즉시 만료시킨다.
- 성공 응답: `204 No Content`
- 클라이언트는 Access Token을 삭제하고 로그인 페이지로 이동한다.

### 5.5 회원 목록 조회

**GET `/api/v1/admin/users`**

| Query Parameter | 타입 | 필수 | 기본값 | 설명 |
|---|---|:---:|---|---|
| `search` | string | X | - | 이메일 또는 이름 부분 검색 |
| `department` | enum | X | - | `RESEARCH`, `MEDICAL`, `DEV` |
| `page` | integer | X | 1 | 페이지 번호, 1 이상 |
| `size` | integer | X | 20 | 페이지 크기, 1~100 |

검색어와 부서 필터는 함께 사용할 수 있다.

성공 응답 — `200 OK`:

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "staff@example.com",
      "name": "홍길동",
      "department": "MEDICAL",
      "gender": "M",
      "phone_number": "010-1234-5678",
      "role": "STAFF",
      "is_active": true
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

- 검색 결과 없음: 빈 `items` 배열과 `200 OK`
- Query Parameter 검증 실패: `422 Unprocessable Entity`
- ADMIN 권한 없음: `403 Forbidden`

### 5.6 회원 권한 변경

**PATCH `/api/v1/admin/users/{user_id}/role`**

요청:

```json
{
  "role": "STAFF"
}
```

성공 응답 — `200 OK`:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "STAFF"
}
```

- 허용되지 않은 권한 값: `422 Unprocessable Entity`
- 대상 회원 없음: `404 Not Found`
- ADMIN 권한 없음: `403 Forbidden`
- 마지막 활성 ADMIN의 권한을 낮춰 관리자 부재가 발생하는 요청: `409 Conflict`

> 화면에서는 여러 회원을 선택할 수 있지만 변경 결과와 오류 대상을 명확히 처리하도록 회원별 단건 호출을 기본으로 한다.

### 5.7 마이페이지 조회

**GET `/api/v1/users/me`**

성공 응답 — `200 OK`:

```json
{
  "name": "홍길동",
  "email": "staff@example.com",
  "department": "MEDICAL",
  "gender": "M",
  "phone_number": "010-1234-5678",
  "role": "STAFF"
}
```

### 5.8 회원 정보 수정

**PATCH `/api/v1/users/me`**

Partial Update이므로 변경할 필드만 보낸다. 수정 가능한 필드는 `department`, `phone_number`뿐이다.

요청 예시:

```json
{
  "department": "RESEARCH",
  "phone_number": "010-9876-5432"
}
```

성공 응답 — `200 OK`: 변경된 정보를 포함한 마이페이지 응답과 동일한 형태로 반환한다.

- 빈 요청 또는 수정 불가 필드 포함: `422 Unprocessable Entity`
- 다른 회원이 사용 중인 휴대폰 번호: `409 Conflict`

### 5.9 비밀번호 변경

**PATCH `/api/v1/users/me/password`**

요청:

```json
{
  "current_password": "Password123!",
  "new_password": "NewPassword456!"
}
```

- 성공 응답: `204 No Content`
- 기존 비밀번호 불일치: `400 Bad Request`
- 새 비밀번호 정책 불충족 또는 기존 비밀번호와 동일: `422 Unprocessable Entity`
- 성공 시 기존 Refresh Token을 모두 폐기하고 쿠키를 만료시킨 뒤 재로그인을 유도한다.

### 5.10 회원 탈퇴

**DELETE `/api/v1/users/me`**

- 요청 본문 없음
- 성공 응답: `204 No Content`
- 하나의 DB 트랜잭션에서 회원과 요구사항상 회원 관련 정보를 즉시 삭제한다.
- 외래키 제약은 명시적인 삭제 순서 또는 `ON DELETE CASCADE`로 처리한다.
- 성공 후 Refresh Token을 폐기하고 쿠키를 만료시킨다.
- 마지막 활성 ADMIN의 탈퇴로 관리자 부재가 발생하는 경우: `409 Conflict`

---

## 6. 공통 오류 응답

```json
{
  "detail": {
    "code": "USER_NOT_FOUND",
    "message": "회원을 찾을 수 없습니다."
  }
}
```

| HTTP 상태 | 사용 기준 |
|---|---|
| `400 Bad Request` | 요청 의미 오류(예: 기존 비밀번호 불일치) |
| `401 Unauthorized` | 토큰 누락·만료·위변조 또는 로그인 실패 |
| `403 Forbidden` | 인증되었으나 권한 부족 또는 비활성 계정 |
| `404 Not Found` | 대상 회원 없음 |
| `409 Conflict` | 이메일·휴대폰 중복, 관리자 부재 등 상태 충돌 |
| `422 Unprocessable Entity` | 형식, enum, 필수값 등 입력 검증 실패 |
| `500 Internal Server Error` | 예상하지 못한 서버 오류 |

운영 환경의 오류 응답에는 비밀번호, 토큰, DB 쿼리, 스택 트레이스 등 민감 정보를 포함하지 않는다.

## 7. 비기능 요구사항 반영

### NFR-USER-001 인증·인가

- Access Token 30분, Refresh Token 7일
- Refresh Token은 HttpOnly 쿠키로 전달
- JWT Payload에는 `user_id`만 저장
- 역할과 계정 활성화 여부는 요청마다 서버 데이터 기준으로 검사

### NFR-USER-002 비밀번호 입력 보안

- 모든 비밀번호 입력은 기본적으로 마스킹한다.
- 보기 아이콘으로 입력값 표시 여부를 전환할 수 있게 한다.
- 비밀번호를 로그, 응답, URL Query Parameter에 기록하지 않는다.
- 서버에는 단방향 비밀번호 해시만 저장한다.

### NFR-USER-003 API 성능

- 모든 User API는 정상 운영 조건에서 요청 수신 후 3초 이내 응답을 목표로 한다.
- 회원 목록에 페이지네이션을 적용한다.
- `users.email`, `users.name`, `users.department` 검색 인덱스를 검토한다.
- 외부 호출에는 명시적 타임아웃을 설정한다.
- API별 처리시간을 모니터링하고 3초 초과 요청을 기록한다.

## 8. 요구사항 추적표

| 요구사항 ID | 반영 API·설계 |
|---|---|
| REQ-USER-001 | `POST /auth/signup` |
| REQ-USER-002 | `POST /auth/login` |
| NFR-USER-001 | `POST /auth/refresh`, JWT·쿠키·권한 정책 |
| REQ-USER-003 | `POST /auth/logout` |
| REQ-USER-004 | `GET /admin/users` |
| REQ-USER-005 | `PATCH /admin/users/{user_id}/role` |
| REQ-USER-006 | `GET /users/me` |
| REQ-USER-007 | `PATCH /users/me` |
| REQ-USER-008 | `PATCH /users/me/password` |
| REQ-USER-009 | `DELETE /users/me` |
| NFR-USER-002 | 비밀번호 입력 및 저장 보안 |
| NFR-USER-003 | 3초 성능 목표, 페이지네이션·인덱스·모니터링 |
