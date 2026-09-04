# worker - 폐렴 예측 추론 워커

흉부 X-ray 이미지를 입력받아 **폐렴(PNEUMONIA) / 정상(NORMAL)** 을 예측하는 **독립 프로세스**다.
인공지능 트랙 과제에서 만든 샘플 CNN 모델(`SimpleCNN`)을 사용한다.

`docs/9일차_동시성문제_해결을위한_아키텍처설계.md` 의 Event-Driven Architecture 에서
**Consumer** 역할을 맡는다. FastAPI(Producer)가 Redis 작업 큐에 넣은 작업을 꺼내
추론하고, 결과를 Pub/Sub 으로 돌려준다. torch 추론이 이 프로세스만 블로킹하므로
FastAPI 이벤트 루프는 영향을 받지 않는다.

```
클라이언트 → FastAPI(Producer) → Redis(Broker/Queue) → worker(Consumer) → 결과 PUBLISH → FastAPI 가 DB 저장·응답
```

## 구성

```
worker/
├── __init__.py
├── model.py                     # 모델 정의 + 로딩(메모리 캐시) + 추론 함수
├── redis_client.py              # Redis 동기 클라이언트 (작업 큐 소비 / 결과 발행)
├── main.py                      # 워커 진입점: while True 로 큐 소비 → 추론 → PUBLISH
├── Dockerfile                   # 추론 전용 최소 이미지 (torch(cpu) 만, fastapi 없음)
├── requirements.txt             # (로컬 설치용) torch / torchvision / pillow
└── models/
    ├── model_state_dict.pth     # ★ 실제 사용하는 학습 가중치 (state_dict)
    └── model.pth                # 전체 모델 pickle (참고용, 코드에서는 사용 안 함)
```

## 작업/결과 프로토콜 (Redis)

| 항목 | 키 / 채널 | 자료구조 | 설명 |
|---|---|---|---|
| 작업 큐 | `pneumonia:task_queue` | List | FastAPI 가 `LPUSH`, 워커가 `BLMOVE`(RIGHT→LEFT)로 소비 |
| 처리중 | `pneumonia:task_queue:processing:{worker_id}` | List | 소비한 작업을 잠시 보관. 완료 시 `LREM`. 비정상 종료 시 다음 기동에서 큐로 복구 |
| 결과 | `pneumonia:result:{job_id}` | Pub/Sub | 워커가 추론 결과(또는 `status:"error"`)를 `PUBLISH` |

작업 payload: `{job_id, record_id, image_url, ai_model, result_channel}`
결과 payload: `{job_id, status:"ok", is_pneumonia, confidence, ai_model}` 또는 `{job_id, status:"error", detail}`

## 실행

```bash
# docker compose (redis + ai-worker 함께)
docker compose up -d redis ai-worker

# 처리량을 늘리려면 워커를 여러 개 (List 큐가 작업을 하나씩 분배)
docker compose up -d --scale ai-worker=3

# 로컬에서 직접
uv sync --only-group ai
REDIS_URL=redis://localhost:6379/0 uv run --no-sync python -m worker.main
```

환경변수: `REDIS_URL`, `PREDICTION_QUEUE_KEY`(기본 `pneumonia:task_queue`),
`MEDIA_BASE_DIR`(공유 media 볼륨 경로, 기본 `/app`).

`model.py` 는 `model_state_dict.pth` 만 사용한다.
`model.pth` 는 전체 객체가 `__main__.SimpleCNN` 으로 pickle 되어 있어 다른 모듈에서
import 하면 로딩이 깨지기 쉽기 때문에, 가중치만 담긴 `state_dict` 를 불러와
`worker/model.py` 안에 정의한 `SimpleCNN` 에 주입하는 방식(파이토치 권장 패턴)을 쓴다.

## 모델 구조 (체크포인트에서 역추출)

| 레이어 | 내용 |
|--------|------|
| conv.0 | `Conv2d(1, 16, kernel_size=3, padding=1)` |
| conv.1 | `ReLU` |
| conv.2 | `MaxPool2d(2, 2)` |
| conv.3 | `Conv2d(16, 32, kernel_size=3, padding=1)` |
| conv.4 | `ReLU` |
| conv.5 | `MaxPool2d(2, 2)` |
| fc.0   | `Flatten` |
| fc.1   | `Linear(32*32*32=32768, 2)` |

- 입력: **1채널(grayscale) 128 x 128** 이미지
- 출력: 2개 클래스 logit → `0 = NORMAL`, `1 = PNEUMONIA`
- 전처리: `Resize((128, 128))` → `Grayscale(1)` → `ToTensor()` (기본값은 [0,1] 스케일만)

> ⚠️ **정규화 값 확인 필요**
> 샘플 모델 학습 노트북에서 `transforms.Normalize(...)` 를 사용했다면,
> `worker/model.py` 상단의 `NORMALIZE_MEAN` / `NORMALIZE_STD` 를 학습 때와 똑같이 채워야
> 확률값이 정확해진다. 현재는 정규화 없이(`None`) 동작한다.

## 설치

```bash
# 저장소 루트에서
uv pip install -r worker/requirements.txt --index-url https://download.pytorch.org/whl/cpu
```

## 사용법

### 1) 파이썬 코드에서

```python
from worker.model import predict

result = predict("media/xray/20250831_chest.png")   # 경로 / bytes / PIL.Image 모두 가능

print(result.is_pneumonia)    # True / False
print(result.label)           # "PNEUMONIA" / "NORMAL"
print(result.confidence)      # 판정 클래스 확률(%) 예: 97.34
print(result.probabilities)   # {"NORMAL": 0.0266, "PNEUMONIA": 0.9734}
print(result.to_dict())       # dict 형태
```

`predict()` 결과 필드는 `ai_analysis_results` 테이블 컬럼
(`is_pneumonia`, `confidence`, `ai_model`)과 그대로 매칭된다.

### 2) CLI (단일 이미지 빠른 확인)

```bash
python -m worker.model media/xray/20250831_chest.png
```

## 동작 방식

- `load_model()` 이 최초 호출 시 `model_state_dict.pth` 를 읽어 `SimpleCNN` 에 로딩하고
  모듈 전역(`_model`)에 캐싱한다. 이후 호출은 메모리에 올라간 인스턴스를 재사용한다.
- GPU 가 있으면 자동으로 CUDA, 없으면 CPU 를 사용한다.
  (가중치는 `map_location="cpu"` 로 불러오므로 GPU 없이도 로딩된다.)
