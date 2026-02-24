import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getConfigSummary, getIssues, type IssueItem } from '../api'

export default function Issues() {
  const [issues, setIssues] = useState<IssueItem[]>([])
  const [repo, setRepo] = useState<string>('')
  const [repos, setRepos] = useState<Array<{ path_with_namespace: string; name: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadIssues = (repoName?: string) => {
    setLoading(true)
    setError('')
    getIssues(repoName)
      .then((data) => {
        setRepo(data.repo)
        setIssues(data.issues)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    getConfigSummary()
      .then((s) => {
        const list = s.repos || []
        setRepos(list)
        if (list.length > 0) {
          loadIssues(list[0].path_with_namespace)
        } else {
          loadIssues()
        }
      })
      .catch(() => loadIssues())
  }, [])

  if (loading) return <div className="text-zinc-400">Загрузка issues…</div>
  if (error) {
    return (
      <div className="rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 text-red-400">
        {error}
        <p className="mt-2 text-sm text-zinc-500">
          Проверьте настройки: выбранный репозиторий и токен в разделе «Настройки».
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-lg font-semibold text-zinc-100">Текущие issues</h2>
        <div className="flex items-center gap-3">
          {repos.length > 0 ? (
            <select
              value={repo}
              onChange={(e) => {
                const nextRepo = e.target.value
                setRepo(nextRepo)
                loadIssues(nextRepo)
              }}
              className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-200"
            >
              {repos.map((r) => (
                <option key={r.path_with_namespace} value={r.path_with_namespace}>
                  {r.path_with_namespace}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-sm text-zinc-500">{repo}</span>
          )}
          <button
            type="button"
            onClick={() => loadIssues(repo || undefined)}
            className="rounded-lg bg-zinc-700 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-600"
          >
            Обновить
          </button>
          <Link
            to="/issues/new"
            className="rounded-lg bg-amber-500 px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-amber-400"
          >
            Новый issue
          </Link>
        </div>
      </div>
      {issues.length === 0 ? (
        <div className="rounded-xl border border-zinc-700 bg-zinc-900/50 p-8 text-center text-zinc-400">
          Нет открытых issues.
        </div>
      ) : (
        <ul className="space-y-3">
          {issues.map((issue) => (
            <li
              key={issue.number}
              className="rounded-xl border border-zinc-700 bg-zinc-900/50 p-4 hover:border-zinc-600 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <a
                    href={issue.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-zinc-100 hover:text-amber-400 truncate block"
                  >
                    #{issue.number} — {issue.title}
                  </a>
                  {issue.body && (
                    <p className="mt-1 text-sm text-zinc-500 line-clamp-2">{issue.body}</p>
                  )}
                  {issue.labels && issue.labels.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {issue.labels.map((label) => (
                        <span
                          key={label}
                          className="rounded bg-zinc-700 px-2 py-0.5 text-xs text-zinc-300"
                        >
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <a
                  href={issue.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-sm text-amber-400 hover:text-amber-300"
                >
                  Открыть →
                </a>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
