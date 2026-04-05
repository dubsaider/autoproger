"""Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.schemas import SettingsResponse, SettingsUpdate
from core.config import get_settings

router = APIRouter(
    prefix="/api/config", tags=["config"], dependencies=[Depends(get_current_user)]
)


def _settings_to_response(s) -> SettingsResponse:
    return SettingsResponse(
        llm_default_provider=s.llm_default_provider,
        llm_default_model=s.llm_default_model,
        log_level=s.log_level,
        claude_code_max_turns_planner=s.claude_code_max_turns_planner,
        claude_code_max_turns_developer=s.claude_code_max_turns_developer,
        claude_code_max_turns_reviewer=s.claude_code_max_turns_reviewer,
        claude_code_max_turns_tester=s.claude_code_max_turns_tester,
        claude_code_budget_planner=s.claude_code_budget_planner,
        claude_code_budget_developer=s.claude_code_budget_developer,
        claude_code_budget_reviewer=s.claude_code_budget_reviewer,
        claude_code_budget_tester=s.claude_code_budget_tester,
    )


@router.get("", response_model=SettingsResponse)
async def read_config():
    return _settings_to_response(get_settings())


@router.patch("", response_model=SettingsResponse)
async def update_config(body: SettingsUpdate):
    s = get_settings()
    for field in body.model_fields_set:
        val = getattr(body, field)
        if val is not None:
            setattr(s, field, val)
    return _settings_to_response(s)
