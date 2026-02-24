"""
Единая точка вызова LLM: Claude API или локальный Cursor CLI.

Выбор через llm_provider: "claude" | "cursor" | "none".
При "cursor" вызывается команда из конфига (например cursor agent -p "...") в каталоге репо.
"""
import shlex
import subprocess
from pathlib import Path
from typing import Literal


def ask(
    prompt: str,
    *,
    provider: Literal["claude", "cursor", "none"] = "none",
    cursor_cli_cmd: str = "cursor agent",
    cursor_cwd: Path | None = None,
    cursor_timeout_sec: int = 120,
    anthropic_api_key: str = "",
    claude_model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    Отправляет prompt в LLM и возвращает ответ (текст).
    При provider="none" или при ошибке возвращает пустую строку.
    """
    if provider == "none":
        return ""

    if provider == "claude":
        if not anthropic_api_key:
            return ""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            msg = client.messages.create(
                model=claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return (msg.content[0].text if msg.content else "") or ""
        except Exception:
            return ""

    if provider == "cursor":
        if not cursor_cli_cmd.strip():
            return ""
        try:
            # -p / --print для вывода ответа в stdout (неинтерактивный режим)
            cmd = shlex.split(cursor_cli_cmd) + ["-p", prompt]
            result = subprocess.run(
                cmd,
                cwd=cursor_cwd or None,
                capture_output=True,
                text=True,
                timeout=cursor_timeout_sec,
            )
            return (result.stdout or "").strip()
        except subprocess.TimeoutExpired:
            return ""
        except FileNotFoundError:
            return ""
        except Exception:
            return ""

    return ""
