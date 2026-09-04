"""AI 추론 워커(worker/) 전용 Redis 동기 클라이언트.

`docs/9일차_동시성문제_해결을위한_아키텍처설계.md` 의 Event-Driven Architecture 에서
워커는 **Consumer** 역할을 맡는다.

- 작업 큐(List, ``TASK_QUEUE_KEY``)에서 작업을 꺼낸다 (``BLMOVE`` / ``BRPOP``).
- 추론 결과를 결과 채널(Pub/Sub)로 발행한다 (``PUBLISH``).

워커는 `while True` 루프로 큐를 지키며 한 번에 한 작업만 처리하므로, 이벤트 루프가
필요 없는 **동기(sync) 클라이언트**를 쓴다. torch 추론이 이 프로세스를 블로킹해도
FastAPI 이벤트 루프에는 영향이 없다.
"""

from __future__ import annotations

import os

import redis

# app(FastAPI) 컨테이너와 같은 값을 쓰도록 환경변수로 맞춘다.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# app 의 settings.PREDICTION_QUEUE_KEY 기본값과 반드시 동일해야 한다.
TASK_QUEUE_KEY = os.environ.get("PREDICTION_QUEUE_KEY", "pneumonia:task_queue")

_client: "redis.Redis | None" = None


def get_redis() -> "redis.Redis":
    """프로세스 전역에서 재사용하는 동기 Redis 커넥션을 반환한다."""
    global _client

    if _client is None:
        _client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            # 블로킹 명령(BLMOVE)은 서버측 timeout 으로만 끊고,
            # 소켓 읽기 자체는 무한 대기시킨다 (조기 TimeoutError 방지).
            socket_timeout=None,
            socket_keepalive=True,
            health_check_interval=30,
        )

    return _client
