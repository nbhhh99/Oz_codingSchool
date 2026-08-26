import uuid as uuid_pkg
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DECIMAL, ForeignKey, String
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.databases import Base
from app.core.db.models import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord


class AiAnalysisResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_analysis_results"

    record_id: Mapped[uuid_pkg.UUID] = mapped_column(
        CHAR(36),
        ForeignKey("medical_records.uuid"),
        nullable=False,
    )
    is_pneumonia: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        DECIMAL(5, 2),
        nullable=False,
    )
    heatmap_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    ai_model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    medical_record: Mapped["MedicalRecord"] = relationship(
        back_populates="ai_analysis_results",
    )