from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_USER: str = "root"
    DB_PASSWORD: str = "password1234"
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "ai_health"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Redis (폐렴 예측 작업 큐 / 결과 Pub-Sub) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    # 폐렴 예측 작업 대기열(List) 키. worker/redis_client.py 의 기본값과 동일해야 한다.
    PREDICTION_QUEUE_KEY: str = "pneumonia:task_queue"
    # 워커가 추론 결과를 발행할 때까지 FastAPI 가 기다리는 최대 시간(초).
    # 초과하면 503 을 반환한다 (작업은 큐에 남아 다른 워커가 이어서 처리).
    PREDICTION_TIMEOUT_SECONDS: float = 60.0

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()