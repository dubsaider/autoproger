"""Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.schemas import SettingsResponse, SettingsUpdate
from core.config import get_settings

router = APIRouter(
    prefix="/api/config", tags=["config"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=SettingsResponse)
async def read_config():
    s = get_settings()
    return SettingsResponse(
        llm_default_provider=s.llm_default_provider,
        llm_default_model=s.llm_default_model,
        log_level=s.log_level,
    )


@router.patch("", response_model=SettingsResponse)
async def update_config(body: SettingsUpdate):
    s = get_settings()
    if body.llm_default_provider is not None:
        s.llm_default_provider = body.llm_default_provider
    if body.llm_default_model is not None:
        s.llm_default_model = body.llm_default_model
    if body.log_level is not None:
        s.log_level = body.log_level
    return SettingsResponse(
        llm_default_provider=s.llm_default_provider,
        llm_default_model=s.llm_default_model,
        log_level=s.log_level,
    )
