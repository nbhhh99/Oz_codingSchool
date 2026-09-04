"""FastAPI(app) 전용 Redis 비동기 클라이언트.

`docs/9일차_동시성문제_해결을위한_아키텍처설계.md` 의 Event-Driven Architecture 에서
FastAPI 는 **Producer** 역할을 맡는다.

- 폐렴 예측 작업을 작업 큐(List, ``settings.PREDICTION_QUEUE_KEY``)에 ``LPUSH`` 한다.
- 결과 채널(Pub/Sub, ``pneumonia:result:{job_id}``)을 ``SUBSCRIBE`` 해 워커가 발행한
  추론 결과를 기다린다.

이벤트 루프를 막지 않도록 ``redis.asyncio`` 를 쓴다. torch 로딩이나 DB 접근은
이 모듈(및 app 프로세스)에서 하지 않는다 — 그것은 worker 의 몫이다.
"""

from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """프로세스 전역에서 재사용하는 비동기 Redis 커넥션 풀을 반환한다."""
    global _client

    if _client is None:
        _client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    return _client


async def close_redis() -> None:
    """앱 종료 시 커넥션 풀을 정리한다 (main.py 의 lifespan 에서 호출)."""
    global _client

    if _client is not None:
        await _client.aclose()
        _client = None
