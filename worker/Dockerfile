# 폐렴 예측 추론 전용 워커 이미지.
#
# FastAPI / SQLAlchemy / Alembic 등 app 의존성은 넣지 않고,
# 추론에 필요한 최소 패키지(torch(cpu), torchvision(cpu), pillow, redis)만 설치한다.
#   → pyproject.toml 의 [dependency-groups].ai 그룹만 `uv sync --only-group ai`
#
# 빌드:  docker build -f worker/Dockerfile -t ai-worker .
# (빌드 컨텍스트는 저장소 루트 — pyproject.toml / uv.lock 을 읽어야 하므로)

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 가상환경을 /app 바깥(/opt/venv)에 둬서, 개발 시 로컬 소스를 /app 으로
# bind-mount 해도 컨테이너가 만든 venv 가 가려지지 않게 한다.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) 의존성만 먼저 설치 — ai 그룹만. (레이어 캐시 활용)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --only-group ai

# 2) 워커 소스 + 모델 가중치 복사
COPY worker/ ./worker/

# app 의 settings 기본값과 맞춘 큐 키. compose 에서 REDIS_URL 을 주입한다.
ENV PREDICTION_QUEUE_KEY=pneumonia:task_queue \
    MEDIA_BASE_DIR=/app \
    PATH="/opt/venv/bin:${PATH}"

CMD ["python", "-m", "worker.main"]
