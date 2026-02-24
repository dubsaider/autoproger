"""Список репозиториев GitHub для выбора в админке."""
from typing import Any


def list_github_repos(token: str, search: str = "") -> list[dict[str, Any]]:
    """Возвращает репозитории текущего пользователя (и доступные ему)."""
    try:
        from github import Github
        gh = Github(token)
        user = gh.get_user()
        repos = list(user.get_repos(sort="updated"))
        result = []
        search_lower = search.strip().lower() if search else ""
        for r in repos:
            full_name = r.full_name
            if search_lower and search_lower not in full_name.lower() and search_lower not in (r.name or "").lower():
                continue
            result.append({
                "id": full_name,
                "path_with_namespace": full_name,
                "name": r.name or full_name,
                "web_url": r.html_url or "",
            })
        return result[:200]
    except Exception:
        return []
