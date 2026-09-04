"""폐렴 예측 추론 워커 진입점.

`docs/9일차_동시성문제_해결을위한_아키텍처설계.md` 의 Event-Driven Architecture 구현체.

    클라이언트 → FastAPI(Producer) → Redis(Broker/Queue) → Worker(Consumer) → 결과 발행

Redis 작업 큐(List)를 `while True` 로 지키다가 작업이 들어오면
`worker.model.predict` 로 추론하고 결과를 결과 채널(Pub/Sub)로 발행한다.
FastAPI 앱과 **별도 프로세스/컨테이너**로 뜨며, torch 추론이 이 프로세스만 블로킹한다.

다중 워커
--------
`docker compose up --scale ai-worker=N` 으로 여러 개를 띄우면, List 큐(`BLMOVE`)가
작업을 워커들에게 하나씩 나눠주므로 처리량이 N 배로 늘어난다. (한 작업은 한 워커만 가져간다.)

비정상 종료 복구 (at-least-once 흉내)
------------------------------------
작업을 큐에서 꺼낼 때 곧바로 버리지 않고 `BLMOVE task_queue -> processing:{worker_id}` 로
워커별 "처리중" 리스트에 옮겨 둔다. 추론·결과 발행이 끝나면 `LREM` 으로 지운다.
워커가 추론 도중 죽으면 그 작업이 처리중 리스트에 남고, 다음 기동 시 큐로 되돌린다.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import time
from typing import Any

import redis

from worker.model import AI_MODEL_NAME, load_model, predict
from worker.redis_client import TASK_QUEUE_KEY, get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

# 워커(프로세스) 식별자 — 컨테이너 hostname + PID 로 유일성 확보
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
PROCESSING_KEY = f"{TASK_QUEUE_KEY}:processing:{WORKER_ID}"

# 공유 media 볼륨 마운트 경로. FastAPI 가 저장한 `/media/xrays/...` 를 여기 기준으로 연다.
MEDIA_BASE_DIR = os.environ.get("MEDIA_BASE_DIR", "/app")

# BLMOVE 블로킹 최대 시간(초). 짧게 끊어 폴링하며 종료 신호를 확인한다.
BLOCK_TIMEOUT = 5

_shutdown = False


def _handle_signal(signum: int, _frame: Any) -> None:
    global _shutdown
    _shutdown = True
    logger.info("종료 신호(%s) 수신 — 현재 작업을 마치고 종료합니다.", signum)


def recover_orphan_tasks(redis_client: Any) -> None:
    """이전 기동에서 처리중이던(=비정상 종료로 남은) 작업을 큐로 되돌린다."""
    moved = 0
    while redis_client.lmove(PROCESSING_KEY, TASK_QUEUE_KEY, "LEFT", "RIGHT") is not None:
        moved += 1
    if moved:
        logger.warning("미완료 작업 %d건을 큐로 복구했습니다. (%s)", moved, PROCESSING_KEY)


def _publish_result(redis_client: Any, channel: str, body: dict[str, Any]) -> None:
    receivers = redis_client.publish(channel, json.dumps(body))
    if receivers == 0:
        # 요청자가 이미 타임아웃돼 구독을 끊은 경우. 결과는 버려지고 FastAPI 가 재요청한다.
        logger.warning("결과를 받을 구독자가 없습니다: channel=%s", channel)


def handle_task(redis_client: Any, raw_task: str) -> None:
    """작업 하나를 추론하고 결과(또는 오류)를 결과 채널로 발행한다."""
    try:
        task = json.loads(raw_task)
    except json.JSONDecodeError:
        logger.exception("작업 JSON 파싱 실패 — 건너뜁니다: %r", raw_task)
        return

    job_id = task.get("job_id", "?")
    result_channel = task.get("result_channel") or f"pneumonia:result:{job_id}"
    image_url = task.get("image_url", "")

    # `/media/xrays/2026/.../x.png` → `/app/media/xrays/2026/.../x.png`
    image_path = os.path.join(MEDIA_BASE_DIR, image_url.lstrip("/\\"))

    started = time.perf_counter()
    try:
        result = predict(image_path)
    except Exception as error:  # noqa: BLE001 - 어떤 추론 오류든 요청자에게 알려야 한다
        logger.exception("추론 실패: job_id=%s image=%s", job_id, image_path)
        _publish_result(
            redis_client,
            result_channel,
            {"job_id": job_id, "status": "error", "detail": str(error)},
        )
        return

    elapsed = time.perf_counter() - started
    logger.info(
        "추론 완료: job_id=%s label=%s confidence=%.2f (%.2fs)",
        job_id,
        result.label,
        result.confidence,
        elapsed,
    )
    _publish_result(
        redis_client,
        result_channel,
        {
            "job_id": job_id,
            "status": "ok",
            "is_pneumonia": bool(result.is_pneumonia),
            "confidence": float(result.confidence),
            "ai_model": AI_MODEL_NAME,
        },
    )


def run() -> None:
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    redis_client = get_redis()
    redis_client.ping()
    logger.info("워커 시작: id=%s queue=%s", WORKER_ID, TASK_QUEUE_KEY)

    recover_orphan_tasks(redis_client)

    # 모델을 미리 로딩해 첫 요청 지연을 없앤다 (메모리에 한 번만 올린다).
    load_model()
    logger.info("모델 로딩 완료 — 작업 대기 중")

    while not _shutdown:
        try:
            raw_task = redis_client.blmove(
                TASK_QUEUE_KEY, PROCESSING_KEY, BLOCK_TIMEOUT, "RIGHT", "LEFT"
            )
        except redis.exceptions.TimeoutError:
            # 큐가 비어 서버측 timeout 으로 반환된 경우 — 정상, 다시 대기한다.
            continue
        except redis.exceptions.ConnectionError:
            logger.warning("Redis 연결 오류 — 1초 후 재시도합니다.")
            time.sleep(1)
            continue

        if raw_task is None:
            continue

        try:
            handle_task(redis_client, raw_task)
        finally:
            # 성공/실패와 무관하게 처리중 리스트에서 제거 (다음 기동 시 중복 복구 방지).
            redis_client.lrem(PROCESSING_KEY, 1, raw_task)

    logger.info("워커 종료: id=%s", WORKER_ID)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("워커가 예기치 않게 종료됩니다.")
        sys.exit(1)
