import enum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.core.db.models import UUIDMixin, TimestampMixin


class GenderEnum(str, enum.Enum):
    M = "M"  # male
    F = "F"  # female


class RoleEnum(str, enum.Enum):
    PENDING = "PENDING"  # 권한 부여 대기
    STAFF = "STAFF"      # 폐렴 추적 관련 데이터 CRUD 허용
    ADMIN = "ADMIN"      # 전체 데이터 CRUD 허용


class DepartmentEnum(str, enum.Enum):
    MEDICAL = "MEDICAL"    # 의료진
    DEV = "DEV"            # 개발팀
    RESEARCH = "RESEARCH"  # 연구진


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(20))
    phone_number: Mapped[str] = mapped_column(String(20), unique=True)

    gender: Mapped[GenderEnum] = mapped_column(Enum(GenderEnum), nullable=False)
    department: Mapped[DepartmentEnum] = mapped_column(Enum(DepartmentEnum), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)