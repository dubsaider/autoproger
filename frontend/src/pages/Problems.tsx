import { useEffect, useState } from 'react'
import { getConfigSummary, scanProblems, type ProblemFinding } from '../api'

type RepoSummary = { path_with_namespace: string; name: string }

function sevClass(sev: string): string {
  const s = (sev || '').toLowerCase()
  if (s === 'critical') return 'text-red-300 border-red-500/50 bg-red-500/10'
  if (s === 'high') return 'text-orange-300 border-orange-500/50 bg-orange-500/10'
  if (s === 'medium') return 'text-amber-300 border-amber-500/50 bg-amber-500/10'
  return 'text-zinc-300 border-zinc-700 bg-zinc-800/30'
}

export default function Problems() {
  const [repos, setRepos] = useState<RepoSummary[]>([])
  const [repo, setRepo] = useState('')
  const [runTests, setRunTests] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [findings, setFindings] = useState<ProblemFinding[]>([])
  const [scannedRepo, setScannedRepo] = useState('')

  useEffect(() => {
    getConfigSummary()
      .then((s) => {
        if (s.ok && s.repos) {
          setRepos(s.repos)
          if (s.repos.length > 0) setRepo(s.repos[0].path_with_namespace)
        }
      })
      .catch(() => {})
  }, [])

  const onScan = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await scanProblems({ repo: repo || undefined, run_tests: runTests })
      setScannedRepo(data.repo)
      setFindings(data.findings || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка сканирования')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">Поиск проблем в репозитории</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Агент ищет потенциальные проблемы: TODO/FIXME, опционально падения тестов и LLM-анализ.
        </p>
      </div>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Репозиторий</label>
            <select
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
              className="w-80 rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            >
              {repos.map((r) => (
                <option key={r.path_with_namespace} value={r.path_with_namespace}>
                  {r.path_with_namespace}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input
              type="checkbox"
              checked={runTests}
              onChange={(e) => setRunTests(e.target.checked)}
              className="rounded text-amber-500"
            />
            Запустить тесты в рамках сканирования
          </label>
          <button
            type="button"
            onClick={onScan}
            disabled={loading}
            className="rounded-lg bg-amber-500 px-5 py-2 font-medium text-zinc-900 hover:bg-amber-400 disabled:opacity-50"
          >
            {loading ? 'Сканирование...' : 'Сканировать'}
          </button>
        </div>
        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-2 text-sm text-red-300">
            {error}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="text-sm text-zinc-500">
          {scannedRepo ? `Результаты для ${scannedRepo}` : 'Сканирование ещё не запускалось'}
        </div>
        {findings.length === 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 text-zinc-400">
            Пока нет найденных проблем.
          </div>
        ) : (
          findings.map((f, idx) => (
            <div key={`${idx}-${f.title}`} className={`rounded-xl border p-4 ${sevClass(f.severity)}`}>
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-medium">{f.title}</h3>
                <span className="text-xs uppercase tracking-wide">{f.severity}</span>
              </div>
              {f.file && <div className="mt-1 text-xs opacity-80">{f.file}</div>}
              <p className="mt-2 text-sm">{f.description}</p>
              {f.hint && <p className="mt-2 text-sm opacity-90">Рекомендация: {f.hint}</p>}
            </div>
          ))
        )}
      </section>
    </div>
  )
}

