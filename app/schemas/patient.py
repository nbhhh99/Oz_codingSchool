import uuid as uuid_pkg
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PatientCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    age: int = Field(ge=0, le=150)
    gender: Literal["male", "female"]
    phone: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("이름을 입력해야 합니다.")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        numbers = value.replace("-", "").strip()

        if not numbers.isdigit() or len(numbers) != 11:
            raise ValueError("연락처는 숫자 11자리여야 합니다.")

        return numbers


class PatientUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=30)
    phone: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("이름을 공백으로 수정할 수 없습니다.")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value

        numbers = value.replace("-", "").strip()

        if not numbers.isdigit() or len(numbers) != 11:
            raise ValueError("연락처는 숫자 11자리여야 합니다.")

        return numbers

    @model_validator(mode="after")
    def validate_update_fields(self):
        if self.name is None and self.phone is None:
            raise ValueError("수정할 항목이 하나 이상 필요합니다.")

        return self


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: uuid_pkg.UUID
    name: str
    age: int
    gender: Literal["male", "female"]
    phone: str
    created_at: datetime
    updated_at: datetime | None


class PatientListResponse(BaseModel):
    items: list[PatientResponse]
    page: int
    size: int
    total: int
    total_pages: int