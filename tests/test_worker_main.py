"""AI 추론 워커(worker/main.py) 단위 테스트.

torch 없이도 큐 소비/결과 발행/비정상 종료 복구 로직을 검증하기 위해
`worker.model` 은 가짜 모듈로, Redis 는 인메모리 Fake 로 대체한다.
"""

import json
import sys
import types
from types import SimpleNamespace

import pytest


class FakeRedis:
    """worker.main 이 쓰는 List / Pub-Sub 명령만 구현한 인메모리 Redis."""

    def __init__(self):
        self.lists: dict[str, list[str]] = {}
        self.published: list[tuple[str, str]] = []

    def ping(self):
        return True

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    def lmove(self, src, dst, src_pos, dst_pos):
        source = self.lists.get(src, [])
        if not source:
            return None
        value = source.pop(0) if src_pos == "LEFT" else source.pop()
        dest = self.lists.setdefault(dst, [])
        dest.insert(0, value) if dst_pos == "LEFT" else dest.append(value)
        return value

    def blmove(self, src, dst, timeout, src_pos, dst_pos):
        return self.lmove(src, dst, src_pos, dst_pos)

    def lrem(self, key, count, value):
        try:
            self.lists.get(key, []).remove(value)
        except ValueError:
            pass

    def publish(self, channel, message):
        self.published.append((channel, message))
        return 1


@pytest.fixture
def worker_main(monkeypatch):
    fake_model = types.ModuleType("worker.model")
    fake_model.AI_MODEL_NAME = "SimpleCNN"
    fake_model.load_model = lambda *a, **k: None

    def _predict(path):
        if "bad" in str(path):
            raise FileNotFoundError(path)
        return SimpleNamespace(is_pneumonia=True, label="PNEUMONIA", confidence=88.0)

    fake_model.predict = _predict
    monkeypatch.setitem(sys.modules, "worker.model", fake_model)
    sys.modules.pop("worker.main", None)

    import worker.main as wm

    yield wm
    sys.modules.pop("worker.main", None)


def test_handle_task_publishes_ok_result(worker_main):
    redis_client = FakeRedis()
    task = json.dumps(
        {
            "job_id": "j1",
            "image_url": "/media/xrays/2026/09/x.png",
            "result_channel": "pneumonia:result:j1",
        }
    )

    worker_main.handle_task(redis_client, task)

    assert len(redis_client.published) == 1
    channel, raw = redis_client.published[0]
    assert channel == "pneumonia:result:j1"
    body = json.loads(raw)
    assert body["status"] == "ok"
    assert body["is_pneumonia"] is True
    assert body["confidence"] == 88.0
    assert body["ai_model"] == "SimpleCNN"


def test_handle_task_publishes_error_on_inference_failure(worker_main):
    redis_client = FakeRedis()
    task = json.dumps(
        {"job_id": "j2", "image_url": "/media/bad.png", "result_channel": "c2"}
    )

    worker_main.handle_task(redis_client, task)

    body = json.loads(redis_client.published[0][1])
    assert body["status"] == "error"
    assert body["job_id"] == "j2"


def test_recover_orphan_tasks_requeues_leftovers(worker_main):
    redis_client = FakeRedis()
    redis_client.lists[worker_main.PROCESSING_KEY] = ["t1", "t2"]

    worker_main.recover_orphan_tasks(redis_client)

    assert redis_client.lists[worker_main.PROCESSING_KEY] == []
    assert set(redis_client.lists[worker_main.TASK_QUEUE_KEY]) == {"t1", "t2"}
