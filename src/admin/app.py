"""FastAPI-приложение админ-панели."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from git import Repo
from git.exc import GitCommandError

from src.admin.auth import (
    create_token,
    get_current_user,
)
from src.admin.config_store import load_config, save_config
from src.admin.github_repos import list_github_repos
from src.admin.gitlab_projects import list_gitlab_projects
from src.connection_config import get_connection_config, get_connection_summary, get_repo_path
from src.repo_client import GitHubRepoClient, GitLabRepoClient
from src.agents.issue_writer import draft_issue
from src.agents.problem_finder import scan_repo_problems
from src.admin.schemas import (
    ConnectionConfig,
    ConfigResponse,
    GitLabProjectsRequest,
    GitHubReposRequest,
    IssueCreateRequest,
    IssueCreateResponse,
    IssueDraftRequest,
    IssueDraftResponse,
    ProblemScanRequest,
    ProblemScanResponse,
    RepoCloneRequest,
    RepoCloneResponse,
    RepoCloneItem,
    LoginRequest,
    LoginResponse,
)

# Логин/пароль админа из .env (один пользователь)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_ENV = os.getenv("ADMIN_PASSWORD", "")
# Если пароль не задан — при первом запуске можно задать через переменную или оставить пустым (небезопасно)


def _check_admin_password(password: str) -> bool:
    if not ADMIN_PASSWORD_ENV:
        return password == "admin"  # дефолт только если не задан ADMIN_PASSWORD
    return password == ADMIN_PASSWORD_ENV


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём data dir при старте
    from src.admin.config_store import _ensure_data_dir
    _ensure_data_dir()
    yield


app = FastAPI(title="Autoproger Admin", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api", tags=["api"])


@api.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    if body.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not _check_admin_password(body.password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = create_token(body.username)
    return LoginResponse(access_token=token)


@api.get("/me")
def me(user: str = Depends(get_current_user)):
    return {"username": user}


@api.get("/config", response_model=ConfigResponse)
def get_config(user: str = Depends(get_current_user)):
    data = load_config()
    config = data.get("connection") or {}
    return ConfigResponse(config=ConnectionConfig.model_validate(config))


@api.get("/config/summary")
def get_config_summary(user: str = Depends(get_current_user)):
    """Сводка конфига без секретов: что реально будет использоваться при запуске пайплайна."""
    return get_connection_summary()


@api.put("/config", response_model=ConfigResponse)
def put_config(body: ConfigResponse, user: str = Depends(get_current_user)):
    data = load_config()
    data["connection"] = body.config.model_dump()
    save_config(data)
    return ConfigResponse(config=body.config)


@api.post("/gitlab/projects")
def gitlab_list_projects(
    body: GitLabProjectsRequest,
    user: str = Depends(get_current_user),
):
    """Список проектов GitLab для выбора репозиториев. Токен в теле, не сохраняется."""
    projects = list_gitlab_projects(body.gitlab_url, body.token, search=body.search)
    return {"projects": projects}


@api.post("/github/repos")
def github_list_repos(
    body: GitHubReposRequest,
    user: str = Depends(get_current_user),
):
    """Список репозиториев GitHub для выбора. Токен в теле, не сохраняется."""
    repos = list_github_repos(body.token, search=body.search)
    return {"repos": repos}


@api.get("/issues")
def list_issues(
    repo: str | None = None,
    labels: str | None = None,
    user: str = Depends(get_current_user),
):
    """Список открытых issues из настроенного репозитория. repo — идентификатор (owner/name или project_id), иначе первый из конфига."""
    try:
        connection = get_connection_config()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not connection.repos:
        raise HTTPException(status_code=400, detail="В конфиге не выбран ни один репозиторий")
    chosen = None
    if repo:
        for r in connection.repos:
            if r.identifier == repo or r.path_with_namespace == repo:
                chosen = r
                break
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Репозиторий не найден: {repo}")
    else:
        chosen = connection.repos[0]
    client = _create_repo_client(connection, chosen)
    label_list = [s.strip() for s in (labels or "").split(",") if s.strip()] or None
    issues = client.list_open_issues(labels=label_list)
    return {
        "repo": chosen.path_with_namespace,
        "issues": [
            {
                "number": i.number,
                "title": i.title,
                "body": (i.body or "")[:500],
                "labels": i.labels,
                "state": i.state,
                "html_url": i.html_url,
            }
            for i in issues
        ],
    }


@api.post("/problems/scan", response_model=ProblemScanResponse)
def scan_problems(
    body: ProblemScanRequest,
    user: str = Depends(get_current_user),
):
    """Поиск потенциальных проблем в репозитории (эвристики + LLM)."""
    try:
        connection = get_connection_config()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not connection.repos:
        raise HTTPException(status_code=400, detail="В конфиге не выбран ни один репозиторий")

    chosen = None
    if body.repo:
        for r in connection.repos:
            if r.identifier == body.repo or r.path_with_namespace == body.repo:
                chosen = r
                break
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Репозиторий не найден: {body.repo}")
    else:
        chosen = connection.repos[0]

    repo_path = get_repo_path(connection, chosen.identifier)
    if not repo_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Локальный путь репозитория не найден: {repo_path}",
        )
    findings = scan_repo_problems(
        repo_path,
        chosen.path_with_namespace,
        llm_provider=connection.llm_provider or "cursor",
        anthropic_api_key=connection.anthropic_api_key or "",
        claude_model=connection.claude_model or "claude-sonnet-4-20250514",
        cursor_cli_cmd=connection.cursor_cli_cmd or "cursor agent",
        cursor_timeout_sec=connection.cursor_timeout_sec or 120,
        run_tests=body.run_tests,
    )
    return ProblemScanResponse(repo=chosen.path_with_namespace, findings=findings)


def _clone_url_for_repo(connection, repo) -> str:
    if connection.provider == "github":
        # GitHub PAT over HTTPS
        return f"https://{connection.github_token}@github.com/{repo.path_with_namespace}.git"
    # GitLab PAT (oauth2 user)
    from urllib.parse import urlsplit
    parts = urlsplit(connection.gitlab_url.rstrip("/"))
    scheme = parts.scheme or "https"
    host = parts.netloc or parts.path
    return f"{scheme}://oauth2:{connection.gitlab_token}@{host}/{repo.path_with_namespace}.git"


def _create_repo_client(connection, repo):
    """Создает API-клиент репозитория без legacy-оркестратора."""
    if connection.provider == "github":
        parts = repo.path_with_namespace.split("/", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=400,
                detail=f"Некорректный идентификатор репозитория: {repo.path_with_namespace}",
            )
        owner, repo_name = parts
        return GitHubRepoClient(owner=owner, repo_name=repo_name, token=connection.github_token)
    if connection.provider == "gitlab":
        return GitLabRepoClient(
            url=connection.gitlab_url,
            project_id=repo.identifier,
            token=connection.gitlab_token,
        )
    raise HTTPException(status_code=400, detail=f"Неизвестный провайдер: {connection.provider}")


@api.post("/repos/clone", response_model=RepoCloneResponse)
def clone_repositories(
    body: RepoCloneRequest,
    user: str = Depends(get_current_user),
):
    """
    Клонировать репозиторий(и) из текущего конфига.
    - clone_all=True: все выбранные
    - repo=...: конкретный
    - иначе: первый выбранный
    """
    try:
        connection = get_connection_config()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not connection.repos:
        raise HTTPException(status_code=400, detail="В конфиге не выбран ни один репозиторий")

    targets = []
    if body.clone_all:
        targets = connection.repos
    elif body.repo:
        for r in connection.repos:
            if r.identifier == body.repo or r.path_with_namespace == body.repo:
                targets = [r]
                break
        if not targets:
            raise HTTPException(status_code=404, detail=f"Репозиторий не найден: {body.repo}")
    else:
        targets = [connection.repos[0]]

    results: list[RepoCloneItem] = []
    for r in targets:
        local_path = get_repo_path(connection, r.identifier)
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            git_dir = local_path / ".git"
            if git_dir.exists():
                if body.pull_if_exists:
                    repo = Repo(local_path)
                    repo.remote("origin").pull()
                    results.append(
                        RepoCloneItem(
                            repo=r.path_with_namespace,
                            local_path=str(local_path),
                            status="pulled",
                            message="Репозиторий уже существовал, выполнен git pull",
                        )
                    )
                else:
                    results.append(
                        RepoCloneItem(
                            repo=r.path_with_namespace,
                            local_path=str(local_path),
                            status="exists",
                            message="Репозиторий уже существует",
                        )
                    )
                continue

            if local_path.exists() and any(local_path.iterdir()):
                results.append(
                    RepoCloneItem(
                        repo=r.path_with_namespace,
                        local_path=str(local_path),
                        status="error",
                        message="Каталог существует и не пустой (нет .git)",
                    )
                )
                continue

            clone_url = _clone_url_for_repo(connection, r)
            Repo.clone_from(clone_url, local_path)
            results.append(
                RepoCloneItem(
                    repo=r.path_with_namespace,
                    local_path=str(local_path),
                    status="cloned",
                    message="Клонирование завершено",
                )
            )
        except GitCommandError as e:
            results.append(
                RepoCloneItem(
                    repo=r.path_with_namespace,
                    local_path=str(local_path),
                    status="error",
                    message=f"Git ошибка: {str(e)[:220]}",
                )
            )
        except Exception as e:
            results.append(
                RepoCloneItem(
                    repo=r.path_with_namespace,
                    local_path=str(local_path),
                    status="error",
                    message=str(e)[:220],
                )
            )
    return RepoCloneResponse(results=results)


@api.post("/issues/draft", response_model=IssueDraftResponse)
def issue_draft(
    body: IssueDraftRequest,
    user: str = Depends(get_current_user),
):
    """Генерация черновика issue через выбранный LLM-агент."""
    if not body.brief.strip():
        raise HTTPException(status_code=400, detail="Поле brief не может быть пустым")
    try:
        connection = get_connection_config()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not connection.repos:
        raise HTTPException(status_code=400, detail="В конфиге не выбран ни один репозиторий")

    chosen = None
    if body.repo:
        for r in connection.repos:
            if r.identifier == body.repo or r.path_with_namespace == body.repo:
                chosen = r
                break
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Репозиторий не найден: {body.repo}")
    else:
        chosen = connection.repos[0]

    drafted = draft_issue(
        body.brief,
        repo_name=chosen.path_with_namespace,
        llm_provider=connection.llm_provider or "cursor",
        anthropic_api_key=connection.anthropic_api_key or "",
        claude_model=connection.claude_model or "claude-sonnet-4-20250514",
        cursor_cli_cmd=connection.cursor_cli_cmd or "cursor agent",
        cursor_timeout_sec=connection.cursor_timeout_sec or 120,
    )
    return IssueDraftResponse(
        title=drafted.get("title", "").strip(),
        body=drafted.get("body", "").strip(),
        labels=list(drafted.get("labels", [])),
        repo=chosen.path_with_namespace,
    )


@api.post("/issues/create", response_model=IssueCreateResponse)
def issue_create(
    body: IssueCreateRequest,
    user: str = Depends(get_current_user),
):
    """Создание issue в выбранном репозитории."""
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Поле title не может быть пустым")
    try:
        connection = get_connection_config()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not connection.repos:
        raise HTTPException(status_code=400, detail="В конфиге не выбран ни один репозиторий")

    chosen = None
    if body.repo:
        for r in connection.repos:
            if r.identifier == body.repo or r.path_with_namespace == body.repo:
                chosen = r
                break
        if not chosen:
            raise HTTPException(status_code=404, detail=f"Репозиторий не найден: {body.repo}")
    else:
        chosen = connection.repos[0]

    client = _create_repo_client(connection, chosen)
    try:
        created = client.create_issue(
            title=body.title.strip(),
            body=body.body or "",
            labels=[s.strip() for s in body.labels if s.strip()],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать issue в {chosen.path_with_namespace}: {str(e)[:400]}",
        )
    if not created:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать issue в {chosen.path_with_namespace} (без подробностей)",
        )
    return IssueCreateResponse(
        number=created.number,
        title=created.title,
        html_url=created.html_url,
        repo=chosen.path_with_namespace,
    )


app.include_router(api)

# Раздаём собранный фронтенд (после npm run build)
_front_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _front_dir.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_front_dir), html=True), name="frontend")
