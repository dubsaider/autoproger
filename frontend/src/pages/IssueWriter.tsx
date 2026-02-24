import { useEffect, useMemo, useState } from 'react'
import { createIssue, draftIssue, getConfigSummary } from '../api'

type RepoSummary = { path_with_namespace: string; name: string }

export default function IssueWriter() {
  const [repos, setRepos] = useState<RepoSummary[]>([])
  const [repo, setRepo] = useState('')
  const [brief, setBrief] = useState('')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [labels, setLabels] = useState('')
  const [loadingDraft, setLoadingDraft] = useState(false)
  const [creating, setCreating] = useState(false)
  const [message, setMessage] = useState('')

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

  const canDraft = brief.trim().length > 3
  const canCreate = title.trim().length > 0

  const labelsList = useMemo(
    () => labels.split(',').map((s) => s.trim()).filter(Boolean),
    [labels]
  )

  const onDraft = async () => {
    if (!canDraft) return
    setLoadingDraft(true)
    setMessage('')
    try {
      const d = await draftIssue(brief, repo || undefined)
      setTitle(d.title)
      setBody(d.body)
      setLabels((d.labels || []).join(', '))
      setMessage('Черновик issue сгенерирован')
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка генерации')
    } finally {
      setLoadingDraft(false)
    }
  }

  const onCreate = async () => {
    if (!canCreate) return
    setCreating(true)
    setMessage('')
    try {
      const created = await createIssue({
        title: title.trim(),
        body: body.trim(),
        labels: labelsList,
        repo: repo || undefined,
      })
      setMessage(`Issue создан: #${created.number} (${created.repo})`)
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка создания issue')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">Новый issue (агент)</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Опиши задачу, агент сгенерирует заголовок/текст issue, затем опубликуй.
        </p>
      </div>

      {message && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 px-4 py-2 text-sm text-zinc-300">
          {message}
        </div>
      )}

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 space-y-4">
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Репозиторий</label>
          <select
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
          >
            {repos.map((r) => (
              <option key={r.path_with_namespace} value={r.path_with_namespace}>
                {r.path_with_namespace}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Что нужно сделать?</label>
          <textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={5}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            placeholder="Например: добавить экспорт отчета в CSV с фильтрами по дате..."
          />
        </div>
        <button
          type="button"
          onClick={onDraft}
          disabled={!canDraft || loadingDraft}
          className="rounded-lg bg-zinc-700 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-600 disabled:opacity-50"
        >
          {loadingDraft ? 'Генерация...' : 'Сгенерировать черновик'}
        </button>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 space-y-4">
        <h3 className="font-medium text-zinc-200">Черновик issue</h3>
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Заголовок</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
          />
        </div>
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Описание</label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={12}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
          />
        </div>
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Метки (через запятую)</label>
          <input
            type="text"
            value={labels}
            onChange={(e) => setLabels(e.target.value)}
            className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            placeholder="bug, enhancement"
          />
        </div>
        <button
          type="button"
          onClick={onCreate}
          disabled={!canCreate || creating}
          className="rounded-lg bg-amber-500 px-6 py-2 font-medium text-zinc-900 hover:bg-amber-400 disabled:opacity-50"
        >
          {creating ? 'Создание...' : 'Создать issue'}
        </button>
      </section>
    </div>
  )
}
