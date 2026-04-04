"""Auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.auth import create_access_token, hash_password, verify_password
from api.schemas import LoginRequest, TokenResponse
from core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_hashed_cache: dict[str, str] = {}


def _get_hashed_admin_pw() -> str:
    s = get_settings()
    if s.admin_password not in _hashed_cache:
        _hashed_cache[s.admin_password] = hash_password(s.admin_password)
    return _hashed_cache[s.admin_password]


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    settings = get_settings()
    if body.username != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    if not verify_password(body.password, _get_hashed_admin_pw()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    token = create_access_token(body.username)
    return TokenResponse(access_token=token)
