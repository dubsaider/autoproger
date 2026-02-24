# Autoproger (новый GitOps-подход)

Проект переведен на новый мультиагентный контур без обратной совместимости со старым CLI.

Текущий поток:

`input -> intake -> router -> analyst -> developer -> tester -> devops -> qa -> quality gates -> branch/push -> PR`

## Ключевые модули

- `orchestrator/main.py` — единый CLI entrypoint
- `orchestrator/router.py` — классификация и маршрутизация задач
- `orchestrator/workflow.py` — цикл выполнения, ретраи, эскалация
- `agents/*` — ролевые агенты
- `workflows/quality_gates.py` — lint/test/build/smoke gate runner
- `integrations/git_client.py` — branch-per-run, commit, push
- `integrations/github_client.py` — создание PR через GitHub API
- `state/*` — модели run/task/gates + JSON store
- `templates/pull_request.md` — шаблон PR

## Запуск

`main.py` теперь делегирует только в новый оркестратор.

### 1) Ручной запуск

```bash
python main.py run --text "Добавить health-check endpoint и smoke-тест" --repo-path "C:\path\to\target-repo" --repo-slug owner/repo
```

### 2) Запуск от GitHub события

```bash
python main.py github-event --event-type issues --payload-file payload.json --repo-path "C:\path\to\target-repo"
```

### 3) Отчет по стабильности/метрикам

```bash
python main.py hardening-report --state-dir state
```

## Полезные флаги

- `--dry-run` — без commit/push/PR
- `--max-retries` — лимит ретраев по задаче
- `--max-cycles` — лимит циклов оркестрации
- `--branch-prefix` — префикс рабочих веток (по умолчанию `auto`)
- `--base-branch` — базовая ветка (по умолчанию `main`)

## Артефакты

- `state/runs/<run_id>.json` — состояние запуска
- `artifacts/<run_id>/` — intake, результаты агентов, quality gates, fail-safe, PR body

## Важно

- Изменения в `main/master` напрямую запрещены политикой `GitClient`.
- PR создается только после прохождения quality gates.
- При фейле срабатывает fail-safe с отчетом в артефакты.
