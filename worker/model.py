"""폐렴(pneumonia) 예측 CNN 모델 로딩 및 추론 모듈.

담당 범위 (오늘의 과제 1단계)
---------------------------------
1. 학습된 모델 파일(``worker/models/model_state_dict.pth``)을 메모리에 한 번만 로딩한다.
2. 업로드된 흉부 X-ray 이미지를 입력받아 폐렴 여부 / 신뢰도를 반환한다.

모델 구조
---------
``model_state_dict.pth`` 의 파라미터 shape 에서 그대로 역추출한 구조이다.
(conv.0.weight = [16, 1, 3, 3], conv.3.weight = [32, 16, 3, 3], fc.1.weight = [2, 32768])

    SimpleCNN(
        conv = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),  # conv.0
            nn.ReLU(),                                             # conv.1
            nn.MaxPool2d(2, 2),                                    # conv.2
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1), # conv.3
            nn.ReLU(),                                             # conv.4
            nn.MaxPool2d(2, 2),                                    # conv.5
        ),
        fc = nn.Sequential(
            nn.Flatten(),                                          # fc.0
            nn.Linear(32 * 32 * 32, 2),                            # fc.1
        ),
    )

- 입력: 1채널(grayscale) 128 x 128 이미지
  (fc.1 의 입력 feature 수 32768 = 32채널 x 32 x 32 이므로 입력 크기는 128 로 고정된다)
- 출력: 2개 클래스에 대한 logit  ->  index 0 = NORMAL(정상), 1 = PNEUMONIA(폐렴)

사용 예시
---------
    from worker.model import predict

    result = predict("media/xray/20250831_chest.png")
    print(result.is_pneumonia, result.confidence)

CLI:
    python -m worker.model media/xray/20250831_chest.png
"""

from __future__ import annotations

import argparse
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms

# --------------------------------------------------------------------------- #
# 설정값
# --------------------------------------------------------------------------- #

# 이 파일(worker/model.py) 기준 가중치 파일 경로
MODEL_DIR = Path(__file__).resolve().parent / "models"
STATE_DICT_PATH = MODEL_DIR / "model_state_dict.pth"

# 체크포인트에서 역산된 값들 (변경 금지)
INPUT_SIZE = 128          # 입력 이미지 한 변 길이 (fc.1 feature 수에서 역산됨)
NUM_CLASSES = 2
CLASS_NAMES = ("NORMAL", "PNEUMONIA")   # index 0 / 1
PNEUMONIA_INDEX = 1

# 학습에 사용한 정규화 값.
#   샘플 모델 학습 노트북과 동일하게 맞춰야 정확한 확률이 나온다.
#   기본값은 "ToTensor 로 [0, 1] 스케일만 적용" 이며, 학습 시 Normalize 를 썼다면
#   아래 두 값을 학습 노트북과 동일하게 채워 넣는다. 예) NORMALIZE_MEAN = (0.5,)
NORMALIZE_MEAN: tuple[float, ...] | None = None
NORMALIZE_STD: tuple[float, ...] | None = None

AI_MODEL_NAME = "SimpleCNN"   # DB(ai_analysis_results.ai_model)에 기록할 모델 식별자
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 이미지로 인식할 입력 타입
ImageInput = Union[str, Path, bytes, bytearray, Image.Image]


# --------------------------------------------------------------------------- #
# 모델 정의
# --------------------------------------------------------------------------- #

class SimpleCNN(nn.Module):
    """model_state_dict.pth 의 키/shape 와 1:1로 대응되는 소형 CNN."""

    def __init__(self, num_classes: int = NUM_CLASSES) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
        )
        # 128 -> (pool) 64 -> (pool) 32,  채널 32  =>  32 * 32 * 32
        flattened = 32 * (INPUT_SIZE // 4) * (INPUT_SIZE // 4)
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(flattened, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        x = self.fc(x)
        return x


# --------------------------------------------------------------------------- #
# 전처리
# --------------------------------------------------------------------------- #

def _build_transform() -> transforms.Compose:
    steps: list = [
        transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
        transforms.Grayscale(num_output_channels=1),
        transforms.ToTensor(),
    ]
    if NORMALIZE_MEAN is not None and NORMALIZE_STD is not None:
        steps.append(transforms.Normalize(NORMALIZE_MEAN, NORMALIZE_STD))
    return transforms.Compose(steps)


_TRANSFORM = _build_transform()


def _to_pil_image(image: ImageInput) -> Image.Image:
    """지원하는 입력 타입을 PIL.Image(grayscale)로 변환한다."""
    if isinstance(image, Image.Image):
        pil_image = image
    elif isinstance(image, (bytes, bytearray)):
        pil_image = Image.open(io.BytesIO(bytes(image)))
    elif isinstance(image, (str, Path)):
        path = Path(image)
        if not path.exists():
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {path}")
        pil_image = Image.open(path)
    else:
        raise TypeError(f"지원하지 않는 이미지 입력 타입입니다: {type(image)!r}")

    return pil_image.convert("L")


# --------------------------------------------------------------------------- #
# 모델 로딩 (메모리 캐시)
# --------------------------------------------------------------------------- #

_model: SimpleCNN | None = None


def load_model(force_reload: bool = False) -> SimpleCNN:
    """학습된 가중치를 SimpleCNN 에 로딩해 반환한다.

    최초 1회만 실제 로딩하고 이후에는 메모리에 올려둔 인스턴스를 재사용한다.
    (FastAPI/워커 프로세스가 살아있는 동안 계속 재사용)
    """
    global _model

    if _model is not None and not force_reload:
        return _model

    if not STATE_DICT_PATH.exists():
        raise FileNotFoundError(
            f"가중치 파일이 없습니다: {STATE_DICT_PATH}\n"
            "모델 파일을 worker/models/ 경로에 복사했는지 확인하세요."
        )

    model = SimpleCNN()
    # 샘플 모델은 GPU(cuda:0)에서 저장됨 -> CPU 환경에서도 로딩되도록 map_location 지정
    state_dict = torch.load(STATE_DICT_PATH, map_location="cpu")
    model.load_state_dict(state_dict)
    model.to(DEVICE)
    model.eval()

    _model = model
    return _model


# --------------------------------------------------------------------------- #
# 추론
# --------------------------------------------------------------------------- #

@dataclass
class PredictionResult:
    """폐렴 예측 결과.

    Attributes:
        is_pneumonia: 폐렴으로 판정되면 True
        label:        "PNEUMONIA" 또는 "NORMAL"
        confidence:   판정 클래스의 확률(%) - 소수 둘째 자리 반올림 (DB confidence 컬럼과 동일 형식)
        probabilities: 클래스별 확률(0~1) 딕셔너리
        ai_model:     사용한 모델 식별자
    """

    is_pneumonia: bool
    label: str
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)
    ai_model: str = AI_MODEL_NAME

    def to_dict(self) -> dict:
        return {
            "is_pneumonia": self.is_pneumonia,
            "label": self.label,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "ai_model": self.ai_model,
        }


@torch.inference_mode()
def predict(image: ImageInput) -> PredictionResult:
    """흉부 X-ray 이미지 한 장에 대해 폐렴 여부를 예측한다.

    Args:
        image: 이미지 파일 경로(str/Path), 이미지 바이트(bytes), 또는 PIL.Image

    Returns:
        PredictionResult
    """
    model = load_model()

    pil_image = _to_pil_image(image)
    tensor = _TRANSFORM(pil_image).unsqueeze(0).to(DEVICE)  # (1, 1, 128, 128)

    logits = model(tensor)
    probs = torch.softmax(logits, dim=1).squeeze(0).cpu()

    pred_index = int(torch.argmax(probs).item())
    probabilities = {name: round(float(probs[i]), 6) for i, name in enumerate(CLASS_NAMES)}

    return PredictionResult(
        is_pneumonia=pred_index == PNEUMONIA_INDEX,
        label=CLASS_NAMES[pred_index],
        confidence=round(float(probs[pred_index]) * 100, 2),
        probabilities=probabilities,
    )


# --------------------------------------------------------------------------- #
# CLI - 로컬에서 단일 이미지 테스트용
# --------------------------------------------------------------------------- #

def _main() -> None:
    parser = argparse.ArgumentParser(
        description="흉부 X-ray 이미지에 대해 폐렴 여부를 예측합니다."
    )
    parser.add_argument("image_path", help="예측할 이미지 파일 경로")
    args = parser.parse_args()

    result = predict(args.image_path)

    print(f"파일        : {args.image_path}")
    print(f"판정        : {result.label} ({'폐렴' if result.is_pneumonia else '정상'})")
    print(f"신뢰도      : {result.confidence:.2f}%")
    print(f"클래스 확률 : {result.probabilities}")
    print(f"모델        : {result.ai_model} / device={DEVICE}")


if __name__ == "__main__":
    _main()
