"""
Единый источник конфигурации подключения к репозиториям.

Приоритет: data/config.json (из админки) → .env.
Если в админке сохранён провайдер и выбран хотя бы один репозиторий — используем это;
иначе — GITHUB_OWNER, GITHUB_REPO, GITHUB_TOKEN, REPO_PATH из .env.
"""
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.admin.config_store import load_config as load_admin_config
from src.config import get_settings


class ResolvedRepo(BaseModel):
    """Один выбранный репозиторий для работы."""
    identifier: str  # для GitHub: "owner/name", для GitLab: str(project_id)
    path_with_namespace: str  # owner/name или group/project
    name: str
    web_url: str = ""


class ResolvedConnectionConfig(BaseModel):
    """Собранная конфигурация подключения (из админки или .env)."""
    provider: str  # "github" | "gitlab"
    # GitHub
    github_token: str = ""
    # GitLab
    gitlab_url: str = ""
    gitlab_token: str = ""
    # Репозитории (хотя бы один)
    repos: list[ResolvedRepo] = Field(default_factory=list)
    # Путь к каталогу с клоном (один репо) или базовый каталог для клонов
    repo_path_base: str = ""
    # Остальное из конфига
    git_author_name: str = ""
    git_author_email: str = ""
    create_draft_mr: bool = True
    issue_labels: list[str] = Field(default_factory=list)
    llm_provider: str = "cursor"  # "claude" | "cursor" | "none"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    cursor_cli_cmd: str = "cursor agent"
    cursor_timeout_sec: int = 120
    actuality_check_llm: bool = False


def _from_env() -> ResolvedConnectionConfig | None:
    """Собрать конфиг из .env (только GitHub, один репозиторий)."""
    s = get_settings()
    if not (s.github_token and s.repo_owner and s.repo_name):
        return None
    return ResolvedConnectionConfig(
        provider="github",
        github_token=s.github_token,
        repos=[
            ResolvedRepo(
                identifier=f"{s.repo_owner}/{s.repo_name}",
                path_with_namespace=f"{s.repo_owner}/{s.repo_name}",
                name=s.repo_name,
                web_url=f"https://github.com/{s.repo_owner}/{s.repo_name}",
            )
        ],
        repo_path_base=str(s.repo_path),
        git_author_name=s.git_author_name,
        git_author_email=s.git_author_email,
        create_draft_mr=s.create_draft_mr,
        issue_labels=s.issue_labels_filter or [],
        llm_provider=getattr(s, "llm_provider", "cursor") or "cursor",
        anthropic_api_key=s.anthropic_api_key,
        claude_model=s.claude_model,
        cursor_cli_cmd=getattr(s, "cursor_cli_cmd", "cursor agent") or "cursor agent",
        cursor_timeout_sec=getattr(s, "cursor_timeout_sec", 120) or 120,
        actuality_check_llm=s.actuality_check_llm,
    )


def _from_admin_file() -> ResolvedConnectionConfig | None:
    """Собрать конфиг из data/config.json (админка)."""
    data = load_admin_config()
    conn = data.get("connection") or {}
    if not conn:
        return None

    provider = conn.get("provider") or "github"
    repos: list[ResolvedRepo] = []

    if provider == "github":
        token = (conn.get("github_token") or "").strip()
        if not token:
            return None
        for r in conn.get("selected_repos") or []:
            path = (r.get("path_with_namespace") or r.get("name") or "").strip()
            if not path:
                continue
            repos.append(
                ResolvedRepo(
                    identifier=path,
                    path_with_namespace=path,
                    name=r.get("name") or path.split("/")[-1],
                    web_url=(r.get("web_url") or ""),
                )
            )
    else:
        token = (conn.get("gitlab_token") or "").strip()
        url = (conn.get("gitlab_url") or "https://gitlab.com").strip()
        if not token:
            return None
        for p in conn.get("selected_projects") or []:
            pid = p.get("id")
            if pid is None:
                continue
            path = (p.get("path_with_namespace") or p.get("name") or str(pid)).strip()
            repos.append(
                ResolvedRepo(
                    identifier=str(pid),
                    path_with_namespace=path,
                    name=p.get("name") or path,
                    web_url=(p.get("web_url") or ""),
                )
            )
        if not repos:
            return None
        return ResolvedConnectionConfig(
            provider="gitlab",
            gitlab_url=url,
            gitlab_token=token,
            repos=repos,
            repo_path_base=(conn.get("repo_path_base") or "").strip(),
            git_author_name=(conn.get("git_author_name") or "").strip(),
            git_author_email=(conn.get("git_author_email") or "").strip(),
            create_draft_mr=conn.get("create_draft_mr", True),
            issue_labels=list(conn.get("issue_labels") or []),
            llm_provider=(conn.get("llm_provider") or "cursor").strip() or "cursor",
            anthropic_api_key=(conn.get("anthropic_api_key") or "").strip(),
            claude_model=(conn.get("claude_model") or "claude-sonnet-4-20250514").strip(),
            cursor_cli_cmd=(conn.get("cursor_cli_cmd") or "cursor agent").strip() or "cursor agent",
            cursor_timeout_sec=int(conn.get("cursor_timeout_sec", 120) or 120),
            actuality_check_llm=conn.get("actuality_check_llm", False),
        )

    if not repos:
        return None
    return ResolvedConnectionConfig(
        provider="github",
        github_token=token,
        repos=repos,
        repo_path_base=(conn.get("repo_path_base") or "").strip(),
        git_author_name=(conn.get("git_author_name") or "").strip(),
        git_author_email=(conn.get("git_author_email") or "").strip(),
        create_draft_mr=conn.get("create_draft_mr", True),
        issue_labels=list(conn.get("issue_labels") or []),
        llm_provider=(conn.get("llm_provider") or "cursor").strip() or "cursor",
        anthropic_api_key=(conn.get("anthropic_api_key") or "").strip(),
        claude_model=(conn.get("claude_model") or "claude-sonnet-4-20250514").strip(),
        cursor_cli_cmd=(conn.get("cursor_cli_cmd") or "cursor agent").strip() or "cursor agent",
        cursor_timeout_sec=int(conn.get("cursor_timeout_sec", 120) or 120),
        actuality_check_llm=conn.get("actuality_check_llm", False),
    )


def get_connection_config() -> ResolvedConnectionConfig:
    """
    Возвращает конфигурацию подключения: сначала из админки (data/config.json),
    при отсутствии или пустом — из .env.
    """
    cfg = _from_admin_file()
    if cfg is not None:
        return cfg
    cfg = _from_env()
    if cfg is not None:
        return cfg
    raise RuntimeError(
        "Нет конфигурации подключения. Настройте репозиторий в админ-панели (Настройки → GitLab/GitHub, выберите репозитории и сохраните) "
        "или задайте в .env: GITHUB_OWNER, GITHUB_REPO, GITHUB_TOKEN и REPO_PATH."
    )


def get_connection_summary() -> dict[str, Any]:
    """
    Краткая сводка конфига без секретов — для отображения «что реально используется».
    Возвращает: { "source": "admin"|"env", "provider", "repos": [...], "repo_path_base", "ok": True }
    или при ошибке: { "ok": False, "error": "..." }.
    """
    try:
        cfg = _from_admin_file()
        source = "admin"
        if cfg is None:
            cfg = _from_env()
            source = "env"
        if cfg is None:
            return {"ok": False, "error": "Конфигурация не задана. Сохраните настройки в админке или заполните .env."}
        return {
            "ok": True,
            "source": source,
            "provider": cfg.provider,
            "repos": [{"path_with_namespace": r.path_with_namespace, "name": r.name} for r in cfg.repos],
            "repo_path_base": cfg.repo_path_base or "(из .env REPO_PATH)",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_repo_path(connection: ResolvedConnectionConfig, repo_identifier: str | None = None) -> Path:
    """Путь к каталогу репозитория. Если один репо — repo_path_base; иначе repo_path_base / slug."""
    base = (connection.repo_path_base or ".").strip()
    if not base:
        s = get_settings()
        base = str(s.repo_path)
    base_path = Path(base).resolve()
    if repo_identifier and len(connection.repos) > 1:
        slug = repo_identifier.replace("/", "-").replace(" ", "_")
        return base_path / slug
    return base_path
