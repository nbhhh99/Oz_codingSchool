import uuid as uuid_pkg
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.databases import Base
from app.core.db.models import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.ai_analysis_result import AiAnalysisResult
    from app.models.patient import Patient
    from app.models.xray_image import XrayImage


class MedicalRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "medical_records"

    patient_id: Mapped[uuid_pkg.UUID] = mapped_column(
        CHAR(36),
        ForeignKey("patients.uuid"),
        nullable=False,
    )
    chart_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    symptoms: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(
        back_populates="medical_records",
    )
    ai_analysis_results: Mapped[list["AiAnalysisResult"]] = relationship(
        back_populates="medical_record",
        cascade="all, delete-orphan",
    )
    xray_images: Mapped[list["XrayImage"]] = relationship(
        back_populates="medical_record",
        cascade="all, delete-orphan",
    )