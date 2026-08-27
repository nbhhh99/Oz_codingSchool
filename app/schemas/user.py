import uuid as uuid_pkg

from pydantic import BaseModel, EmailStr, field_validator, model_validator

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

class UserRoleUpdateRequest(BaseModel):
    role: RoleEnum


class UserUpdateRequest(BaseModel):
    department: DepartmentEnum | None = None
    phone_number: str | None = None

    @model_validator(mode="after")
    def validate_update_fields(self):
        if self.department is None and self.phone_number is None:
            raise ValueError("수정할 항목이 하나 이상 필요합니다.")
        return self

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str | None) -> str | None:
        if value is None:
            return value

        numbers = value.replace("-", "")
        if not numbers.isdigit() or len(numbers) not in (10, 11):
            raise ValueError("올바른 휴대폰 번호 형식이 아닙니다.")

        return value


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("새 비밀번호는 최소 8자 이상이어야 합니다.")
        return value

    @model_validator(mode="after")
    def validate_passwords_are_different(self):
        if self.current_password == self.new_password:
            raise ValueError("새 비밀번호는 기존 비밀번호와 달라야 합니다.")
        return self


class UserRoleResponse(BaseModel):
    uuid: uuid_pkg.UUID
    role: RoleEnum

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: list[UserResponse]
    page: int
    size: int
    total: int
    total_pages: int