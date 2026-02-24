"""Агент подготовки текста issue (черновик) через LLM."""
from pathlib import Path

from src.llm import ask


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _template_draft(brief: str) -> dict:
    short = (brief or "").strip() or "Улучшение функциональности"
    title = short[:80]
    body = (
        "## Контекст\n"
        f"{short}\n\n"
        "## Ожидаемое поведение\n"
        "- Реализовать улучшение так, чтобы оно давало заметный результат для пользователя.\n"
        "- Обновить связанную логику без регрессий.\n\n"
        "## Критерии приемки\n"
        "- [ ] Функциональность реализована и проверена локально.\n"
        "- [ ] Добавлены или обновлены тесты.\n"
        "- [ ] Документация/описание изменений обновлены при необходимости.\n"
    )
    return {"title": title, "body": body, "labels": ["enhancement"]}


def _parse_draft(text: str, fallback_brief: str) -> dict:
    title = ""
    body = ""
    labels: list[str] = []
    current = None

    for raw in text.splitlines():
        line = raw.rstrip()
        upper = line.upper().strip()
        if upper.startswith("TITLE:"):
            current = "title"
            title = line.split(":", 1)[-1].strip()
            continue
        if upper.startswith("BODY:"):
            current = "body"
            body = line.split(":", 1)[-1].strip()
            continue
        if upper.startswith("LABELS:"):
            current = "labels"
            labels_line = line.split(":", 1)[-1].strip()
            labels = [s.strip() for s in labels_line.split(",") if s.strip()]
            continue
        if current == "body":
            body += ("\n" if body else "") + line
        elif current == "labels" and line.strip():
            labels.extend([s.strip() for s in line.split(",") if s.strip()])

    if not title:
        title = fallback_brief[:80].strip() or "Новый issue"
    if not body:
        body = fallback_brief.strip()
    labels = list(dict.fromkeys(labels))[:10]

    # Защита от "копии запроса": если LLM вернул почти тот же текст,
    # подставляем структурированный шаблон issue.
    if _norm(body) == _norm(fallback_brief) or len(body.strip()) < 40:
        templ = _template_draft(fallback_brief)
        title = title if _norm(title) != _norm(fallback_brief) else templ["title"]
        body = templ["body"]
        labels = labels or templ["labels"]

    return {"title": title, "body": body, "labels": labels}


def draft_issue(
    brief: str,
    *,
    repo_name: str,
    llm_provider: str = "cursor",
    anthropic_api_key: str = "",
    claude_model: str = "claude-sonnet-4-20250514",
    cursor_cli_cmd: str = "cursor agent",
    cursor_timeout_sec: int = 120,
    cursor_cwd: Path | None = None,
) -> dict:
    """Генерирует черновик issue: title/body/labels."""
    prompt = f"""Сгенерируй issue для репозитория {repo_name}.

Задача от пользователя:
{brief}

Требования:
- Не копируй запрос пользователя дословно.
- Раскрой задачу в структурированном виде: контекст, ожидаемое поведение, критерии приемки.
- Заголовок должен быть конкретным и понятным.

Ответь строго в формате:
TITLE: короткий конкретный заголовок
BODY:
подробное описание задачи (Markdown, с критериями приемки)
LABELS: bug, enhancement, docs
"""
    text = ask(
        prompt,
        provider=llm_provider if llm_provider in ("claude", "cursor", "none") else "none",
        cursor_cli_cmd=cursor_cli_cmd,
        cursor_cwd=cursor_cwd,
        cursor_timeout_sec=cursor_timeout_sec,
        anthropic_api_key=anthropic_api_key,
        claude_model=claude_model,
    )
    if not text:
        return _template_draft(brief)
    return _parse_draft(text, brief)
