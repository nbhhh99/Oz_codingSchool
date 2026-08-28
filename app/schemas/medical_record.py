import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class XrayImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: uuid_pkg.UUID
    url: str = Field(validation_alias="image_url")
    shooting_datetime: datetime
    created_at: datetime


class MedicalRecordCreateResponse(BaseModel):
    uuid: uuid_pkg.UUID
    patient_id: uuid_pkg.UUID
    chart_number: str
    symptoms: str
    xray_image: XrayImageResponse
    created_at: datetime


class MedicalRecordListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: uuid_pkg.UUID
    chart_number: str
    symptoms: str
    created_at: datetime


class MedicalRecordListResponse(BaseModel):
    items: list[MedicalRecordListItem]
    page: int
    size: int
    total: int
    total_pages: int


class MedicalRecordDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: uuid_pkg.UUID
    patient_id: uuid_pkg.UUID
    chart_number: str
    symptoms: str
    xray_images: list[XrayImageResponse]
    created_at: datetime