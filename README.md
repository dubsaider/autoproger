# Autoproger v2

Multi-agent system for automated software development and maintenance. Watches issues in GitHub/GitLab repositories, processes them through an AI agent pipeline, and creates Pull Requests.

## Architecture

```
Issue Watcher → Task Manager → Orchestrator
                                  ├── Planner Agent
                                  ├── Developer Agent
                                  ├── Reviewer Agent (loop)
                                  └── Tester Agent
                                          ↓
                               Quality Gates → PR/MR
```

**LLM Abstraction Layer** — pluggable providers:
- Anthropic API (Claude)
- Claude Code CLI
- OpenRouter (access to many models)

**Interfaces:**
- Web Dashboard (React + Tailwind)
- Telegram Bot
- REST API + Webhooks

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your tokens

# 2. Run with Docker
docker compose up --build

# 3. Or run locally
pip install -e .
python main.py
```

Open http://localhost:8000 — login with credentials from `.env`.

## Configuration

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENROUTER_API_KEY` | OpenRouter API key (fallback) |
| `LLM_DEFAULT_PROVIDER` | `anthropic`, `claude_code`, or `openrouter` |
| `LLM_DEFAULT_MODEL` | Model name (e.g. `claude-sonnet-4-20250514`) |
| `DATABASE_URL` | Database URL (SQLite or PostgreSQL) |
| `SECRET_KEY` | JWT secret |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Dashboard credentials |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_ADMIN_CHAT_ID` | Chat ID for notifications |
| `GITHUB_TOKEN` | GitHub personal access token |
| `GITLAB_TOKEN` | GitLab access token |

## How It Works

1. **Issue Watcher** polls configured repos for issues with target labels (e.g. `autoproger`)
2. **Task Manager** creates a task; in `semi_auto` mode waits for approval
3. **Orchestrator** runs the agent pipeline:
   - **Planner** analyzes the issue and codebase, creates an implementation plan
   - **Developer** generates code changes
   - **Reviewer** reviews for bugs/security issues (up to 2 rounds)
   - **Tester** generates tests
4. **Quality Gates** run lint/test checks
5. System creates a branch, commits, pushes, and opens a PR

## Project Structure

```
core/           — orchestrator, task manager, config, domain models
agents/         — AI agents (planner, developer, reviewer, tester)
llm/            — LLM abstraction layer and providers
integrations/   — GitHub/GitLab clients, repo manager, issue watcher
context/        — codebase indexer and context builder
quality/        — quality gate runner
storage/        — database models and CRUD
api/            — FastAPI REST API
bot/            — Telegram bot
frontend/       — React dashboard
```
