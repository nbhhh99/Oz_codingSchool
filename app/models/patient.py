from typing import TYPE_CHECKING

from sqlalchemy import Enum, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.databases import Base
from app.core.db.models import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord


class Patient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "patients"

    name: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    age: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    gender: Mapped[str | None] = mapped_column(
        Enum("male", "female", name="gender"),
        nullable=True,
    )

    phone: Mapped[str] = mapped_column(
        String(11),
        nullable=False,
    )

    medical_records: Mapped[list["MedicalRecord"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )