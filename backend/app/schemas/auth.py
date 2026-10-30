from pydantic import BaseModel, EmailStr, Field, field_validator


def _pw(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(v.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes.")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str

    _v = field_validator("password")(_pw)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str

    _v = field_validator("new_password")(_pw)
