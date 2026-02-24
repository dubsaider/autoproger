import { useState, useEffect } from 'react'
import {
  getConfig,
  saveConfig,
  getConfigSummary,
  fetchGitLabProjects,
  fetchGitHubRepos,
  cloneRepos,
  type ConnectionConfig,
  type ConfigSummary,
  type RepoCloneItem,
  type RepoItem,
} from '../api'

const defaultConfig: ConnectionConfig = {
  provider: 'gitlab',
  gitlab_url: 'https://gitlab.com',
  gitlab_token: '',
  selected_projects: [],
  github_token: '',
  selected_repos: [],
  repo_path_base: '',
  git_author_name: '',
  git_author_email: '',
  create_draft_mr: true,
  issue_labels: [],
  llm_provider: 'cursor',
  anthropic_api_key: '',
  claude_model: 'claude-sonnet-4-20250514',
  cursor_cli_cmd: 'cursor agent',
  cursor_timeout_sec: 120,
  actuality_check_llm: false,
}

export default function Dashboard() {
  const [config, setConfig] = useState<ConnectionConfig>(defaultConfig)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [gitlabProjects, setGitlabProjects] = useState<Array<{ id: number; path_with_namespace: string; name: string; web_url: string }>>([])
  const [loadingProjects, setLoadingProjects] = useState(false)
  const [projectSearch, setProjectSearch] = useState('')
  const [githubRepos, setGithubRepos] = useState<Array<{ id: string; path_with_namespace: string; name: string; web_url: string }>>([])
  const [loadingRepos, setLoadingRepos] = useState(false)
  const [repoSearch, setRepoSearch] = useState('')
  const [summary, setSummary] = useState<ConfigSummary | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [cloning, setCloning] = useState(false)
  const [cloneResults, setCloneResults] = useState<RepoCloneItem[]>([])

  const loadSummary = async () => {
    setSummaryLoading(true)
    try {
      const s = await getConfigSummary()
      setSummary(s)
    } catch {
      setSummary({ ok: false, error: 'Не удалось загрузить сводку' })
    } finally {
      setSummaryLoading(false)
    }
  }

  useEffect(() => {
    getConfig()
      .then((r) => setConfig(r.config))
      .catch(() => setMessage('Ошибка загрузки конфига'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!loading) loadSummary()
  }, [loading])

  const update = (patch: Partial<ConnectionConfig>) => {
    setConfig((c) => ({ ...c, ...patch }))
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage('')
    try {
      await saveConfig(config)
      setMessage('Конфигурация сохранена')
      loadSummary()
      setTimeout(() => setMessage(''), 3000)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const handleCloneSelected = async () => {
    setCloning(true)
    setMessage('')
    setCloneResults([])
    try {
      const r = await cloneRepos({ clone_all: true, pull_if_exists: true })
      setCloneResults(r.results || [])
      if ((r.results || []).some((x) => x.status === 'error')) {
        setMessage('Клонирование завершено с ошибками')
      } else {
        setMessage('Клонирование/обновление завершено')
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка клонирования')
    } finally {
      setCloning(false)
    }
  }

  const loadGitLabProjects = async () => {
    if (!config.gitlab_url || !config.gitlab_token) {
      setMessage('Укажите URL GitLab и токен')
      return
    }
    setLoadingProjects(true)
    setMessage('')
    try {
      const { projects } = await fetchGitLabProjects(
        config.gitlab_url,
        config.gitlab_token,
        projectSearch
      )
      setGitlabProjects(projects)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка загрузки проектов')
    } finally {
      setLoadingProjects(false)
    }
  }

  const toggleProject = (proj: (typeof gitlabProjects)[0]) => {
    const exists = config.selected_projects.some(
      (p) => String(p.id) === String(proj.id) && p.path_with_namespace === proj.path_with_namespace
    )
    if (exists) {
      update({
        selected_projects: config.selected_projects.filter(
          (p) => !(String(p.id) === String(proj.id) && p.path_with_namespace === proj.path_with_namespace)
        ),
      })
    } else {
      update({
        selected_projects: [
          ...config.selected_projects,
          {
            id: proj.id,
            name: proj.name,
            path_with_namespace: proj.path_with_namespace,
            web_url: proj.web_url || '',
          },
        ],
      })
    }
  }

  const removeSelected = (item: RepoItem) => {
    update({
      selected_projects: config.selected_projects.filter(
        (p) => !(String(p.id) === String(item.id) && p.path_with_namespace === item.path_with_namespace)
      ),
    })
  }

  const loadGitHubRepos = async () => {
    if (!config.github_token) {
      setMessage('Укажите GitHub токен')
      return
    }
    setLoadingRepos(true)
    setMessage('')
    try {
      const { repos } = await fetchGitHubRepos(config.github_token, repoSearch)
      setGithubRepos(repos)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка загрузки репозиториев')
    } finally {
      setLoadingRepos(false)
    }
  }

  const toggleRepo = (repo: (typeof githubRepos)[0]) => {
    const exists = config.selected_repos.some(
      (r) => String(r.id) === String(repo.id) && r.path_with_namespace === repo.path_with_namespace
    )
    if (exists) {
      update({
        selected_repos: config.selected_repos.filter(
          (r) => !(String(r.id) === String(repo.id) && r.path_with_namespace === repo.path_with_namespace)
        ),
      })
    } else {
      update({
        selected_repos: [
          ...config.selected_repos,
          { id: repo.id, name: repo.name, path_with_namespace: repo.path_with_namespace, web_url: repo.web_url || '' },
        ],
      })
    }
  }

  const removeSelectedRepo = (item: RepoItem) => {
    update({
      selected_repos: config.selected_repos.filter(
        (r) => !(String(r.id) === String(item.id) && r.path_with_namespace === item.path_with_namespace)
      ),
    })
  }

  if (loading) return <div className="text-zinc-400">Загрузка...</div>

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">Настройки системы</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Подключение к GitLab (или GitHub), выбор репозиториев и параметры пайплайна.
        </p>
      </div>

      {message && (
        <div
          className={`rounded-lg border px-4 py-2 text-sm ${
            message.includes('Ошибка') ? 'border-red-500/50 text-red-400' : 'border-emerald-500/50 text-emerald-400'
          }`}
        >
          {message}
        </div>
      )}

      {/* Что реально используется при запуске CLI */}
      <section className="rounded-xl border border-zinc-700 bg-zinc-900/30 p-4">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3 className="font-medium text-zinc-200">Что используется при запуске пайплайна</h3>
          <button
            type="button"
            onClick={loadSummary}
            disabled={summaryLoading}
            className="text-sm text-amber-400 hover:text-amber-300 disabled:opacity-50"
          >
            {summaryLoading ? 'Загрузка…' : 'Проверить'}
          </button>
        </div>
        {summary && (
          <div className="mt-3 text-sm">
            {summary.ok ? (
              <div className="space-y-1 text-zinc-300">
                <p>
                  <span className="text-zinc-500">Источник:</span>{' '}
                  {summary.source === 'admin' ? 'админка (data/config.json)' : '.env'}
                </p>
                <p>
                  <span className="text-zinc-500">Провайдер:</span> {summary.provider}
                </p>
                <p>
                  <span className="text-zinc-500">Репозитории:</span>{' '}
                  {summary.repos?.length
                    ? summary.repos.map((r) => r.path_with_namespace).join(', ')
                    : '—'}
                </p>
                <p>
                  <span className="text-zinc-500">Каталог:</span> {summary.repo_path_base || '—'}
                </p>
              </div>
            ) : (
              <p className="text-amber-400">{summary.error}</p>
            )}
          </div>
        )}
      </section>

      {/* Провайдер */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h3 className="font-medium text-zinc-200 mb-4">Репозиторий</h3>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="provider"
              checked={config.provider === 'gitlab'}
              onChange={() => update({ provider: 'gitlab' })}
              className="text-amber-500"
            />
            <span>GitLab</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="provider"
              checked={config.provider === 'github'}
              onChange={() => update({ provider: 'github' })}
              className="text-amber-500"
            />
            <span>GitHub</span>
          </label>
        </div>

        {config.provider === 'gitlab' && (
          <div className="mt-6 space-y-4">
            <div>
              <label className="block text-sm text-zinc-400 mb-1">URL сервера GitLab</label>
              <input
                type="url"
                value={config.gitlab_url}
                onChange={(e) => update({ gitlab_url: e.target.value })}
                className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                placeholder="https://gitlab.com"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Personal Access Token</label>
              <input
                type="password"
                value={config.gitlab_token}
                onChange={(e) => update({ gitlab_token: e.target.value })}
                className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                placeholder="glpat-..."
              />
              <p className="text-xs text-zinc-500 mt-1">Токен хранится в конфиге админки (data/config.json)</p>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Поиск проектов</label>
                <input
                  type="text"
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  placeholder="название"
                  className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 w-48 focus:border-amber-500 focus:outline-none"
                />
              </div>
              <button
                type="button"
                onClick={loadGitLabProjects}
                disabled={loadingProjects}
                className="rounded-lg bg-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50"
              >
                {loadingProjects ? 'Загрузка...' : 'Загрузить проекты'}
              </button>
            </div>
            {gitlabProjects.length > 0 && (
              <div className="mt-4 rounded-lg border border-zinc-700 max-h-60 overflow-y-auto">
                <div className="p-2 bg-zinc-800/50 text-xs text-zinc-400 sticky top-0">
                  Выберите репозитории для работы
                </div>
                <ul className="divide-y divide-zinc-700">
                  {gitlabProjects.map((proj) => {
                    const selected = config.selected_projects.some(
                      (p) => String(p.id) === String(proj.id) && p.path_with_namespace === proj.path_with_namespace
                    )
                    return (
                      <li key={`${proj.id}-${proj.path_with_namespace}`} className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-800/50">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleProject(proj)}
                          className="text-amber-500 rounded"
                        />
                        <span className="text-zinc-300 truncate flex-1">{proj.path_with_namespace}</span>
                        <a
                          href={proj.web_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-amber-400 hover:underline text-sm shrink-0"
                        >
                          Открыть
                        </a>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}
            {config.selected_projects.length > 0 && (
              <div className="mt-2">
                <span className="text-sm text-zinc-400">Выбрано: </span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {config.selected_projects.map((p) => (
                    <span
                      key={`${p.id}-${p.path_with_namespace}`}
                      className="inline-flex items-center gap-1 rounded bg-zinc-700 px-2 py-0.5 text-sm"
                    >
                      {p.path_with_namespace || p.name}
                      <button
                        type="button"
                        onClick={() => removeSelected(p)}
                        className="text-zinc-400 hover:text-red-400"
                        aria-label="Удалить"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {config.provider === 'github' && (
          <div className="mt-6 space-y-4">
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Personal Access Token</label>
              <input
                type="password"
                value={config.github_token}
                onChange={(e) => update({ github_token: e.target.value })}
                className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                placeholder="ghp_..."
              />
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Поиск репозиториев</label>
                <input
                  type="text"
                  value={repoSearch}
                  onChange={(e) => setRepoSearch(e.target.value)}
                  placeholder="название"
                  className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 w-48 focus:border-amber-500 focus:outline-none"
                />
              </div>
              <button
                type="button"
                onClick={loadGitHubRepos}
                disabled={loadingRepos}
                className="rounded-lg bg-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50"
              >
                {loadingRepos ? 'Загрузка...' : 'Загрузить репозитории'}
              </button>
            </div>
            {githubRepos.length > 0 && (
              <div className="mt-4 rounded-lg border border-zinc-700 max-h-60 overflow-y-auto">
                <div className="p-2 bg-zinc-800/50 text-xs text-zinc-400 sticky top-0">
                  Выберите репозитории для работы
                </div>
                <ul className="divide-y divide-zinc-700">
                  {githubRepos.map((repo) => {
                    const selected = config.selected_repos.some(
                      (r) => String(r.id) === String(repo.id) && r.path_with_namespace === repo.path_with_namespace
                    )
                    return (
                      <li key={repo.id} className="flex items-center gap-2 px-3 py-2 hover:bg-zinc-800/50">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleRepo(repo)}
                          className="text-amber-500 rounded"
                        />
                        <span className="text-zinc-300 truncate flex-1">{repo.path_with_namespace}</span>
                        <a
                          href={repo.web_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-amber-400 hover:underline text-sm shrink-0"
                        >
                          Открыть
                        </a>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}
            {config.selected_repos.length > 0 && (
              <div className="mt-2">
                <span className="text-sm text-zinc-400">Выбрано: </span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {config.selected_repos.map((r) => (
                    <span
                      key={`${r.id}-${r.path_with_namespace}`}
                      className="inline-flex items-center gap-1 rounded bg-zinc-700 px-2 py-0.5 text-sm"
                    >
                      {r.path_with_namespace || r.name}
                      <button
                        type="button"
                        onClick={() => removeSelectedRepo(r)}
                        className="text-zinc-400 hover:text-red-400"
                        aria-label="Удалить"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-6 border-t border-zinc-800 pt-4">
          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={handleCloneSelected}
              disabled={cloning}
              className="rounded-lg bg-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50"
            >
              {cloning ? 'Клонирование...' : 'Клонировать выбранные репозитории'}
            </button>
            <p className="text-xs text-zinc-500">
              Используется текущий сохранённый конфиг. Если репозиторий уже существует — выполняется pull.
            </p>
          </div>
          {cloneResults.length > 0 && (
            <div className="mt-3 space-y-2">
              {cloneResults.map((r, i) => (
                <div
                  key={`${r.repo}-${i}`}
                  className={`rounded-md border px-3 py-2 text-xs ${
                    r.status === 'error'
                      ? 'border-red-500/40 text-red-300'
                      : 'border-zinc-700 text-zinc-300'
                  }`}
                >
                  <div className="font-medium">{r.repo}</div>
                  <div className="opacity-80">{r.local_path}</div>
                  <div>
                    [{r.status}] {r.message}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Общие настройки */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h3 className="font-medium text-zinc-200 mb-4">Пайплайн и коммиты</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Базовый каталог репозиториев (REPO_PATH)</label>
            <input
              type="text"
              value={config.repo_path_base}
              onChange={(e) => update({ repo_path_base: e.target.value })}
              className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
              placeholder="C:\repos или /home/user/repos"
            />
          </div>
          <div className="flex gap-4 flex-wrap">
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Имя автора коммитов</label>
              <input
                type="text"
                value={config.git_author_name}
                onChange={(e) => update({ git_author_name: e.target.value })}
                className="w-56 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                placeholder="Autoproger Bot"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-400 mb-1">Email автора</label>
              <input
                type="email"
                value={config.git_author_email}
                onChange={(e) => update({ git_author_email: e.target.value })}
                className="w-64 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                placeholder="bot@users.noreply.github.com"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.create_draft_mr}
              onChange={(e) => update({ create_draft_mr: e.target.checked })}
              className="rounded text-amber-500"
            />
            <span className="text-zinc-300">Создавать MR как черновик (draft)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={config.actuality_check_llm}
              onChange={(e) => update({ actuality_check_llm: e.target.checked })}
              className="rounded text-amber-500"
            />
            <span className="text-zinc-300">Проверять актуальность issue через LLM</span>
          </label>
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Метки issues (фильтр, через запятую)</label>
            <input
              type="text"
              value={config.issue_labels.join(', ')}
              onChange={(e) =>
                update({
                  issue_labels: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                })
              }
              className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
              placeholder="bug, feature"
            />
          </div>
        </div>
      </section>

      {/* LLM: Cursor (локально) или Claude API */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h3 className="font-medium text-zinc-200 mb-4">LLM для анализа и планов</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Источник</label>
            <div className="flex gap-4 flex-wrap">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="llm_provider"
                  checked={config.llm_provider === 'cursor'}
                  onChange={() => update({ llm_provider: 'cursor' })}
                  className="text-amber-500"
                />
                <span>Cursor (локальный CLI)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="llm_provider"
                  checked={config.llm_provider === 'claude'}
                  onChange={() => update({ llm_provider: 'claude' })}
                  className="text-amber-500"
                />
                <span>Claude API</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="llm_provider"
                  checked={config.llm_provider === 'none'}
                  onChange={() => update({ llm_provider: 'none' })}
                  className="text-amber-500"
                />
                <span>Без LLM (шаблонный план)</span>
              </label>
            </div>
          </div>
          {config.llm_provider === 'cursor' && (
            <>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Команда Cursor CLI</label>
                <input
                  type="text"
                  value={config.cursor_cli_cmd}
                  onChange={(e) => update({ cursor_cli_cmd: e.target.value })}
                  className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                  placeholder="cursor agent"
                />
                <p className="text-xs text-zinc-500 mt-1">Запускается в каталоге репозитория. Установка: cursor.com/docs/cli</p>
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Таймаут (сек)</label>
                <input
                  type="number"
                  min={30}
                  max={600}
                  value={config.cursor_timeout_sec}
                  onChange={(e) => update({ cursor_timeout_sec: parseInt(e.target.value, 10) || 120 })}
                  className="w-24 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                />
              </div>
            </>
          )}
          {config.llm_provider === 'claude' && (
            <>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Anthropic API Key</label>
                <input
                  type="password"
                  value={config.anthropic_api_key}
                  onChange={(e) => update({ anthropic_api_key: e.target.value })}
                  className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                  placeholder="sk-ant-..."
                />
              </div>
              <div>
                <label className="block text-sm text-zinc-400 mb-1">Модель</label>
                <input
                  type="text"
                  value={config.claude_model}
                  onChange={(e) => update({ claude_model: e.target.value })}
                  className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 focus:border-amber-500 focus:outline-none"
                />
              </div>
            </>
          )}
        </div>
      </section>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg bg-amber-500 px-6 py-2 font-medium text-zinc-900 hover:bg-amber-400 disabled:opacity-50"
        >
          {saving ? 'Сохранение...' : 'Сохранить конфигурацию'}
        </button>
        <p className="text-sm text-zinc-500">
          Конфиг сохраняется в data/config.json. Для применения в CLI можно экспортировать в .env или использовать запуск пайплайна из админки (позже).
        </p>
      </div>
    </div>
  )
}
