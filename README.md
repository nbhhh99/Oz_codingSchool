# AI 헬스케어 웹 서비스 — 폐렴 예측

흉부 X-Ray 이미지를 업로드하면 AI 모델(`SimpleCNN`)이 **폐렴 여부**를 예측해 주는
사내용 웹 서비스입니다. 회원/권한 관리, 환자·진료기록 관리, X-Ray 업로드,
AI 폐렴 예측 및 결과 조회 기능을 제공합니다.

| 구분 | 사용 기술 |
|---|---|
| 백엔드 | FastAPI, SQLAlchemy(async), Alembic |
| DB / 브로커 | MySQL 8.0, Redis 7 |
| AI 워커 | PyTorch(CPU), torchvision, Pillow — FastAPI와 분리된 독립 프로세스 |
| 패키지 관리 | uv (`pyproject.toml` + `uv.lock`) |
| 인프라 | Docker, docker-compose |
| 협업 | GitHub Flow (feature 브랜치 → PR → 리뷰 → `main` 병합) |

아키텍처 도식: [`docs/images/9일차_eda_아키텍처.svg`](docs/images/9일차_eda_아키텍처.svg)

---

## 프로젝트 진행 단계 총정리

AI 웹 서비스를 만드는 과정을 아래 10단계로 세분화하고, 각 단계를 팀에서
**어떤 방식으로 진행했는지** 정리했습니다. 모든 산출물(문서 포함)은 예외 없이
`feature`/`docs` 브랜치에서 작업한 뒤 **PR을 올리고, 작성자가 아닌 다른 팀원이
리뷰**한 후 `main`에 병합했습니다. AI Agent는 보조 도구로 활용하되, 병합 전
팀원 전체가 해당 산출물을 이해하는 것을 원칙으로 했습니다.

| 단계 | 내용 | 상태 | 주요 산출물 |
|---|---|---|---|
| 1 | Team Rule 정의 | ✅ 완료 | `docs/1일차_team_rules.md` |
| 2 | 사용자 요구사항 정의 | ✅ 완료 | 요구사항 정의서(REQ/NFR ID 체계) |
| 3 | API 명세서 작성 | ✅ 완료 | `docs/4·5·6일차_*_API_설계.md` |
| 4 | Git & GitHub Branch 전략 구성 | ✅ 완료 | `docs/2일차_git_branch_전략.md` |
| 5 | 프로젝트 세팅 | ✅ 완료 | `docs/3일차_*`, `pyproject.toml`, `alembic/` |
| 6 | API·AI 워커 코드 작성 + Branch 전략 병합 | ✅ 완료 | `app/`, `worker/`, `tests/` (PR #14~#21) |
| 7 | 아키텍처 설계 및 적용 | ✅ 완료 | `docs/9일차_*`, `worker/`, Redis 큐 (PR #26~#30) |
| 8 | 도커 인프라 파일 작성 | ✅ 완료 | `app/Dockerfile`, `worker/Dockerfile`, `docker-compose.yml` |
| 9 | AWS 배포 | ⏳ 예정 | — |
| 10 | QA 진행 | ⏳ 예정 | — |

---

### 1. Team Rule 정의

- 프로젝트 킥오프에서 팀원이 함께 협업 규칙을 논의하고 [`docs/1일차_team_rules.md`](docs/1일차_team_rules.md)에 명문화했습니다.
- 규칙은 10개 영역으로 나눴습니다: 기본 원칙, 역할·업무 분담, Git 브랜치 규칙, Commit 규칙, Push/PR 규칙, 코드 작성 규칙, 보안 규칙, 소통 규칙, 일정·완료 기준, 문제 해결 원칙.
- 핵심 합의:
  - 하나의 업무엔 한 명의 담당자를 두고 진행 상황을 투명하게 공유한다.
  - 다른 팀원의 코드를 수정해야 하면 먼저 상의한다.
  - 커밋 메시지는 `타입: 작업 내용` 형식(`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`).
  - 민감정보(`.env`, 키, 토큰)는 커밋하지 않고 `.env.example`로만 항목을 공유한다.

### 2. 사용자 요구사항 정의

- 제공된 **요구사항 정의서**를 팀원이 함께 읽고 해석하는 세션을 가졌습니다. (이번 프로젝트에선 정의서가 주어졌지만, 이후 프로젝트에선 직접 작성해야 함을 확인)
- 요구사항을 **ID 체계**로 관리해 명세·구현·QA까지 추적 가능하도록 했습니다.
  - 기능: `REQ-USER-*`(회원/권한), `REQ-PTNT-*`(환자), `REQ-MDR-*`(진료기록/X-Ray), `REQ-PRED-*`(AI 폐렴 예측)
  - 비기능: `NFR-*` — 예: `NFR-PRED-001` 모델 평가 기준(Recall ≥ 0.90, Accuracy ≥ 0.80), `NFR-PRED-002` 모든 API 3초 이내 응답
- 각 API 설계 문서 말미에 **요구사항 추적표**를 두어 "어떤 요구사항이 어떤 API/설계로 반영되었는지" 매핑했습니다.

### 3. API 명세서 작성

- 구현 전에 API 계약을 먼저 확정했습니다. 도메인별로 문서를 나눠 담당자를 지정하고, 명세 PR → 팀 리뷰 → `main` 병합 후에 구현에 착수했습니다.
  - [`docs/4일차_USER_API_설계.md`](docs/4일차_USER_API_설계.md) — 회원가입/로그인/토큰재발급/로그아웃/회원관리/마이페이지
  - [`docs/5일차_환자관리_API_설계.md`](docs/5일차_환자관리_API_설계.md) — 환자 CRUD, 진료기록·X-Ray 등록/조회
  - [`docs/6일차_폐렴예측_API_설계.md`](docs/6일차_폐렴예측_API_설계.md) — AI 폐렴 예측 실행/조회
- 문서 포맷을 통일했습니다: **문서 개요 → 공통 정책(Enum·인증/인가·입력 검증·페이지네이션) → API 목록 표 → 상세 명세(요청/응답/오류) → 공통 오류 응답 → 비기능 요구사항 반영 → 요구사항 추적표**.
- 6일차 명세 리뷰에서 인증·인가 섹션 누락, 엔드포인트 중첩 구조 불일치, 모델 식별자 불일치 등을 지적하고 반영 후 병합한 사례처럼, 리뷰가 실제 수정으로 이어지도록 운영했습니다.

### 4. Git & GitHub Branch 전략 구성

- [`docs/2일차_git_branch_전략.md`](docs/2일차_git_branch_전략.md)에서 Git Flow와 GitHub Flow를 비교하고, **짧은 실습 프로젝트 규모**에 맞춰 **GitHub Flow**를 채택했습니다.
- 규칙:
  - `main`은 항상 실행 가능한 상태로 유지하고, 직접 push하지 않는다.
  - 기능/문서/수정 하나당 브랜치 하나: `feature/기능명`, `docs/문서명`, `fix/수정내용`, `refactor/대상`.
  - 브랜치 이름은 영문 소문자 + 하이픈.
  - PR은 **작성자가 아닌 다른 팀원**이 리뷰하고, 요구사항대로 동작하는지 확인 후 Approve. 수정이 필요하면 Request changes.
- 실제로 이 저장소의 모든 변경은 PR #1 이후 30여 개의 PR을 통해 병합되었습니다.

### 5. 프로젝트 세팅

- [`docs/3일차_프로젝트_뜯어보기.md`](docs/3일차_프로젝트_뜯어보기.md)에서 스켈레톤 코드의 디렉터리·파일 역할을 팀이 함께 분석했습니다.
- **레이어드 아키텍처**를 확정했습니다:
  `app/apis`(라우터) → `app/services`(비즈니스 로직) → `app/repositories`(DB 접근) → `app/models`(ORM). 요청/응답 형태는 `app/schemas`(Pydantic).
- 공통 기반:
  - `app/core/config.py` — `pydantic-settings`로 `.env` 로딩
  - `app/core/db/databases.py` — async 엔진/세션(`asyncmy`), `async_get_db` 의존성
  - `app/core/db/models.py` — `UUIDMixin`(CHAR(36) + `uuid7`), `TimestampMixin`
  - `uv` + `pyproject.toml` + `uv.lock`로 의존성 고정
- DB 마이그레이션 흐름([`docs/3일차_db_migration.md`](docs/3일차_db_migration.md)): 모델 작성 → `app/models/__init__.py`에 등록 → `uv run alembic revision --autogenerate` → `uv run alembic upgrade head` → DB Viewer(TablePlus)로 스키마 확인 → PR 병합.

### 6. API 및 AI 워커 코드 작성 후 Branch 전략을 통한 코드 병합

각 기능을 담당자별 `feature` 브랜치에서 구현하고, 명세서에 정의한 계약대로
동작하는지 확인한 뒤 PR·리뷰를 거쳐 `main`에 병합했습니다.

| 기능 | 브랜치·PR | 요약 |
|---|---|---|
| 인증 / 회원 관리 API | `feat/auth-api`, `feature/user-management-apis` (PR #14·#15) | 회원가입·로그인·토큰 재발급·로그아웃·마이페이지·회원 권한 변경. JWT + bcrypt |
| 환자 / 진료기록 API | `feature/patient-medical-record-apis` (PR #17) | 환자 CRUD, 진료기록·X-Ray `multipart` 업로드, 파일 시그니처 검증, `/media` 저장 |
| AI 워커 추론 코드 | `feature/worker-pneumonia-inference` (PR #18) | 체크포인트에서 역추출한 `SimpleCNN` 정의, `model_state_dict.pth` 로딩(메모리 캐시), `predict()` — 이미지 경로/bytes/PIL 입력, `is_pneumonia`/`confidence` 반환 |
| 폐렴 예측 API | `feature/ai-prediction-api` (PR #20) | `POST .../{record_id}/ai-prediction`(실행/캐시), `GET .../ai-predictions`(목록). `(record_id, ai_model)` 캐시로 재추론 방지 |
| 프론트 템플릿 연결 | `feature/connect-frontend-template-apis` (PR #21) | `static/`의 화면을 실제 API에 연결. 경로/enum/응답 형태 차이를 어댑터 레이어에서 흡수 |

- 테스트: `tests/`에 SQLite + ASGI 통합 테스트와 단위 테스트를 두어, MySQL 없이도 라우터~서비스~리포지토리 흐름과 상태코드 분기(201/200/404/422)를 검증했습니다.
- 실행 화면은 [`docs/7일차_앱_실행화면.md`](docs/7일차_앱_실행화면.md)에 회원가입부터 AI 예측 결과까지 캡처했습니다.

### 7. 아키텍처 설계 및 적용

- **문제 인식**: SimpleCNN 추론은 CPU-bound 동기 연산이라, FastAPI 프로세스 안에서 직접 돌리면 여러 요청이 동시에 들어올 때 이벤트 루프가 막혀 다른 API까지 느려지고 `NFR-PRED-002`(3초) 위반 위험이 있었습니다.
- **설계**: [`docs/9일차_동시성문제_해결을위한_아키텍처설계.md`](docs/9일차_동시성문제_해결을위한_아키텍처설계.md)에서 Event-Driven Architecture를 정리하고 도식화했습니다.

  ```
  Client → FastAPI(Producer) → Redis(작업 큐 List + 결과 Pub/Sub) → AI Worker(Consumer) → MySQL
  ```

- **적용**:
  - AI 추론을 **별도 워커 프로세스/이미지**로 분리 (`worker/main.py`, `worker/redis_client.py`) — PR #29
  - FastAPI는 작업을 큐에 `LPUSH`하고 결과 채널을 `SUBSCRIBE`해서 대기, torch를 import하지 않음
  - 워커는 `BLMOVE`로 작업을 꺼내(비정상 종료 시 다음 기동에서 복구) 추론 후 결과를 `PUBLISH`
  - 동시 요청은 Redis 분산 잠금으로 직렬화하고, 잠금 획득 후 캐시를 재확인해 중복 추론·중복 저장 방지 (PR #30)
  - `torch`를 `pyproject.toml`의 `[dependency-groups].ai`로 분리 → FastAPI 이미지엔 torch 미포함, 워커 이미지엔 CPU 전용 휠만 설치해 두 이미지 용량 최소화

### 8. 도커 인프라 관련 파일 작성

- **`app/Dockerfile`** — `python:3.13-slim` + `uv`, 2-스테이지(`uv sync --no-install-project` → 소스 복사 → `uv sync`)로 레이어 캐시 활용. venv를 `/opt/venv`에 둬서 bind-mount가 가려지지 않게 함.
- **`worker/Dockerfile`** — `uv sync --only-group ai`로 추론 패키지만 설치한 최소 이미지.
- **`.dockerignore`** — 빌드 컨텍스트 루트(저장소 루트)에 배치해 실제 적용되도록 수정(PR #24). `.env`, 캐시, `.venv`, `.git`, `docs/`, `media/` 제외.
- **`docker-compose.yml`** — 4개 서비스:
  - `fastapi` — `.:/app` bind-mount + `alembic upgrade head` 후 `uvicorn --reload`, `mysql`/`redis` `service_healthy` 대기
  - `ai-worker` — `worker/Dockerfile` 빌드, `--scale ai-worker=N`으로 수평 확장
  - `mysql` — `mysql:8.0`, `utf8mb4`, `mysql_volume` 영속화, `mysqladmin ping` 헬스체크
  - `redis` — `redis:7-alpine`, AOF 영속화(`redis_volume`)
  - 업로드 X-Ray는 `media_volume`을 fastapi·ai-worker가 공유
- 실행 확인: [`docs/8일차_도커_실행화면.md`](docs/8일차_도커_실행화면.md), [`docs/8일차_도커컴포즈_실행화면.md`](docs/8일차_도커컴포즈_실행화면.md)

### 9. AWS 배포 (예정)

아직 착수하지 않았습니다. 현재까지의 도커 구성을 기반으로 다음과 같이 진행할 계획입니다.

- 이미지: `app`, `ai-worker` 이미지를 **ECR**에 푸시
- 실행: **ECS(Fargate)** 또는 EC2 — `fastapi` 서비스와 `ai-worker` 서비스(오토스케일)로 분리
- 관리형 리소스: **RDS(MySQL)**, **ElastiCache(Redis)**
- 시크릿: `.env` 대신 **SSM Parameter Store / Secrets Manager**
- 업로드 파일: 공유 스토리지(**EFS**) 또는 저장 방식을 **S3**로 전환
- 산출물 예정: `docs/AWS_배포.md`, IaC 또는 배포 스크립트

### 10. QA 진행 (예정)

아직 착수하지 않았습니다. 계획은 다음과 같습니다.

- **요구사항 추적표 기반 시나리오 QA** — REQ/NFR ID별로 정상·예외 케이스 점검표 작성
- **자동화 테스트 확대** — 현재 `tests/`는 AI 예측 위주 → 인증/환자/진료기록 API까지 커버리지 확대
- **비기능 검증** — `NFR-PRED-002`(3초) 부하·동시성 테스트, `NFR-PRED-001`(Recall/Accuracy) 모델 평가 리포트
- **배포 환경 스모크 테스트** — 배포 후 핵심 플로우(회원가입→환자 등록→X-Ray 업로드→AI 예측) 확인
- 산출물 예정: `docs/QA_체크리스트.md`, QA 결과 리포트

---

## 로컬 실행

### docker-compose (권장)

```bash
cp .env.example .env          # 값 확인/수정
docker compose up --build     # fastapi + mysql + redis + ai-worker
# http://localhost:8000  (API 문서: /docs)
```

### 직접 실행

```bash
uv sync                                   # FastAPI 앱 의존성
uv run alembic upgrade head               # 스키마 반영 (MySQL 필요)
uv run fastapi dev app/main.py            # 개발 서버

# AI 워커 (별도 터미널)
uv sync --only-group ai
REDIS_URL=redis://localhost:6379/0 uv run --no-sync python -m worker.main
```

### 테스트

```bash
uv pip install -r tests/requirements.txt -r worker/requirements.txt
uv run pytest
```

## DB 마이그레이션

```bash
# 모델(app/models/) 변경 후 마이그레이션 파일 생성
uv run alembic revision --autogenerate -m "변경 내용 설명"

# 데이터베이스에 반영
uv run alembic upgrade head

# 마지막 마이그레이션 되돌리기
uv run alembic downgrade -1
```

## 디렉터리 구조

```
app/
├── apis/            # FastAPI 라우터 (요청 검증 · 응답 직렬화)
├── services/        # 비즈니스 로직
├── repositories/    # DB 접근 (SQLAlchemy)
├── models/          # ORM 모델
├── schemas/         # Pydantic 요청/응답 모델
├── core/            # 설정 · DB 세션 · Redis 클라이언트 · 공통 Mixin
└── Dockerfile
worker/              # AI 추론 워커 (독립 프로세스, torch)
├── model.py         # SimpleCNN 정의 + predict()
├── main.py          # Redis 큐 소비 루프
├── redis_client.py
└── Dockerfile
alembic/versions/    # DB 마이그레이션
tests/               # pytest (SQLite + ASGI)
docs/                # 팀 규칙 · Git 전략 · API 명세 · 아키텍처 · 실행화면
static/              # 프론트엔드 템플릿
docker-compose.yml   # fastapi + mysql + redis + ai-worker
```
