"""Получение списка проектов GitLab для выбора в админке."""
from typing import Any


def list_gitlab_projects(url: str, token: str, search: str = "") -> list[dict[str, Any]]:
    """Возвращает список проектов GitLab (id, path_with_namespace, name, web_url)."""
    import gitlab
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()
        opts = {"get_all": True}
        if search:
            opts["search"] = search
        projects = gl.projects.list(**opts)
        return [
            {
                "id": p.id,
                "path_with_namespace": p.path_with_namespace,
                "name": p.name,
                "web_url": getattr(p, "web_url", "") or "",
            }
            for p in projects
        ]
    except Exception:
        return []
