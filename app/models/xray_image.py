import uuid as uuid_pkg
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.databases import Base
from app.core.db.models import UUIDMixin

if TYPE_CHECKING:
    from app.models.medical_record import MedicalRecord
    from app.models.user import User


class XrayImage(UUIDMixin, Base):
    __tablename__ = "xray_images"

    record_id: Mapped[uuid_pkg.UUID] = mapped_column(
        CHAR(36),
        ForeignKey("medical_records.uuid"),
        nullable=False,
    )

    uploader_id: Mapped[uuid_pkg.UUID] = mapped_column(
        CHAR(36),
        ForeignKey("users.uuid"),
        nullable=False,
    )

    image_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    shooting_datetime: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("current_timestamp(0)"),
    )

    medical_record: Mapped["MedicalRecord"] = relationship(
        back_populates="xray_images",
    )

    uploader: Mapped["User"] = relationship(
        back_populates="uploaded_xray_images",
    )