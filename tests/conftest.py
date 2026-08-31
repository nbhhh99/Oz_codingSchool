"""AI 예측 API 테스트용 공용 픽스처.

메인 앱은 MySQL(asyncmy)을 사용하지만, 테스트는 인메모리 SQLite로 스키마를
새로 만들어 라우터~서비스~리포지토리~DB 흐름을 검증한다.
실제 모델 추론(`worker.model.predict`)은 테스트에서 스텁으로 대체한다.
"""

import uuid as uuid_pkg
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db.databases import Base, async_get_db
from app.main import app
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.user import DepartmentEnum, RoleEnum, User
from app.models.xray_image import XrayImage
from app.services.patient_service import get_current_staff

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite 어댑터 보정:
    #  - MySQL 전용 문법 current_timestamp(0) → CURRENT_TIMESTAMP
    #  - CHAR(36) 컬럼에 바인딩되는 uuid.UUID 객체 → str (asyncmy는 허용, sqlite3는 거부)
    def _coerce(value):
        return str(value) if isinstance(value, uuid_pkg.UUID) else value

    @event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def _fix_for_sqlite(_conn, _cursor, statement, parameters, _context, executemany):
        if "current_timestamp(0)" in statement:
            statement = statement.replace(
                "current_timestamp(0)", "CURRENT_TIMESTAMP"
            )

        def _fix_one(params):
            if isinstance(params, dict):
                return {k: _coerce(v) for k, v in params.items()}
            if isinstance(params, (list, tuple)):
                return type(params)(_coerce(v) for v in params)
            return params

        if executemany and isinstance(parameters, (list, tuple)):
            parameters = type(parameters)(_fix_one(p) for p in parameters)
        else:
            parameters = _fix_one(parameters)

        return statement, parameters

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def _override_get_db():
        yield db_session

    fake_user = User(
        uuid=str(uuid_pkg.uuid4()),
        email="staff@example.com",
        hashed_password="x",
        name="테스터",
        phone_number="01000000000",
        gender="M",
        department=DepartmentEnum.RESEARCH,
        role=RoleEnum.STAFF,
        is_active=True,
    )

    app.dependency_overrides[async_get_db] = _override_get_db
    app.dependency_overrides[get_current_staff] = lambda: fake_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_record(db_session: AsyncSession):
    """환자 + 진료기록 + X-Ray 1장을 생성하고 각 id를 돌려준다."""
    patient = Patient(
        uuid=str(uuid_pkg.uuid4()),
        name="김환자",
        age=45,
        gender="male",
        phone="01012345678",
    )
    db_session.add(patient)
    await db_session.flush()

    record = MedicalRecord(
        uuid=str(uuid_pkg.uuid4()),
        patient_id=patient.uuid,
        chart_number="CHART-TEST-001",
        symptoms="기침, 발열",
    )
    db_session.add(record)
    await db_session.flush()

    xray = XrayImage(
        uuid=str(uuid_pkg.uuid4()),
        record_id=record.uuid,
        uploader_id=str(uuid_pkg.uuid4()),
        image_url="/media/xrays/2026/08/31/test.png",
        shooting_datetime=datetime(2026, 8, 31, 9, 30, tzinfo=UTC),
    )
    db_session.add(xray)
    await db_session.commit()

    return {
        "patient_id": patient.uuid,
        "record_id": record.uuid,
        "xray_url": xray.image_url,
    }
