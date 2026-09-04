import uuid as uuid_pkg
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DECIMAL, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.databases import Base
from app.core.db.models import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord


class AiAnalysisResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ai_analysis_results"

    # 캐시 조회(record_id + ai_model)용 복합 인덱스 (NFR-PRED-002)
    __table_args__ = (
        Index(
            "ix_ai_analysis_results_record_id_ai_model",
            "record_id",
            "ai_model",
        ),
    )

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
    # 히트맵 생성은 이후 단계 → 선택 사항이므로 nullable (REQ-PRED-001, 설계서 7장)
    heatmap_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    ai_model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    medical_record: Mapped["MedicalRecord"] = relationship(
        back_populates="ai_analysis_results",
    )