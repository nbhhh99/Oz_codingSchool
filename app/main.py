import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.apis.practice_apis import router as practice_router
from app.apis.auth_apis import router as auth_router
from app.apis.user_apis import router as user_router
from app.apis.patient_apis import router as patient_router
from app.apis.medical_record_apis import router as medical_record_router
from app.apis.ai_prediction_apis import router as ai_prediction_router
from app.core.redis_client import close_redis


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 폐렴 예측 작업 큐/결과 Pub-Sub 용 Redis 커넥션은 첫 요청 때 지연 생성되고,
    # 앱 종료 시 여기서 정리한다.
    yield
    await close_redis()


app = FastAPI(lifespan=lifespan)
app.include_router(practice_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(patient_router)
app.include_router(medical_record_router)
app.include_router(ai_prediction_router)

BASE_DIR = Path(__file__).resolve().parent.parent

# 만약 static, media 폴더가 존재하지 않으면 생성
if not (BASE_DIR / "static").exists():
    os.mkdir(BASE_DIR / "static")
if not (BASE_DIR / "media").exists():
    os.mkdir(BASE_DIR / "media")

# 'static' 폴더를 '/static' 경로로 마운트 (CSS, JS 파일 서빙용)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
# 'media' 폴더를 '/media' 경로로 마운트 (사용자 업로드 파일 서빙용)
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")


@app.get(path="/healthcheck", status_code=200, include_in_schema=False)
async def healthcheck():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/{path:path}", include_in_schema=False)
async def catch_all(path: str):
    # API나 정적 파일 경로는 제외 (FastAPI가 먼저 매칭하지 못한 경우에만 실행됨)
    if (
        path.startswith("api/v1")
        or path.startswith("static/")
        or path.startswith("media/")
    ):
        raise HTTPException(status_code=404)
    return FileResponse(BASE_DIR / "static" / "index.html")