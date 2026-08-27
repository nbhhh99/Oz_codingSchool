import uuid as uuid_pkg

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import DepartmentEnum, GenderEnum, RoleEnum


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    department: DepartmentEnum
    gender: GenderEnum
    phone_number: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 최소 8자 이상이어야 합니다.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    uuid: uuid_pkg.UUID
    email: EmailStr
    name: str
    department: DepartmentEnum
    gender: GenderEnum
    phone_number: str
    role: RoleEnum
    is_active: bool

    class Config:
        from_attributes = True