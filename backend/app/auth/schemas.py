from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    mfa_required: bool


class MfaVerifyRequest(BaseModel):
    code: str


class UserOut(BaseModel):
    id: str
    username: str
