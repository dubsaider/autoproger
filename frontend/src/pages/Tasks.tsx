import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [filter, setFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [repos, setRepos] = useState<any[]>([]);
  const [form, setForm] = useState({ repo_id: "", issue_title: "", issue_body: "" });
  const [formError, setFormError] = useState("");

  const load = () => {
    const params: Record<string, string> = {};
    if (filter) params.status = filter;
    api.listTasks(params).then(setTasks).catch(() => {});
  };

  useEffect(() => { load(); }, [filter]);

  useEffect(() => {
    if (showForm) api.listRepos().then(setRepos).catch(() => {});
  }, [showForm]);

  const approve = async (id: string) => {
    await api.approveTask(id);
    load();
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    try {
      await api.createTask(form);
      setShowForm(false);
      setForm({ repo_id: "", issue_title: "", issue_body: "" });
      load();
    } catch (err: any) {
      setFormError(err.message ?? "Error");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Tasks</h2>
        <div className="flex items-center gap-3">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {showForm ? "Cancel" : "New task"}
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 space-y-4">
          <h3 className="text-white font-semibold">Create task</h3>
          <label className="block">
            <span className="text-sm text-gray-400">Repository</span>
            <select
              value={form.repo_id}
              onChange={(e) => setForm({ ...form, repo_id: e.target.value })}
              className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              required
            >
              <option value="">Select repository...</option>
              {repos.map((r) => (
                <option key={r.id} value={r.id}>{r.url}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Title</span>
            <input
              type="text"
              value={form.issue_title}
              onChange={(e) => setForm({ ...form, issue_title: e.target.value })}
              placeholder="What needs to be done?"
              className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              required
            />
          </label>
          <label className="block">
            <span className="text-sm text-gray-400">Description</span>
            <textarea
              value={form.issue_body}
              onChange={(e) => setForm({ ...form, issue_body: e.target.value })}
              placeholder="Detailed description of the task..."
              rows={4}
              className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white resize-none"
            />
          </label>
          {formError && <p className="text-red-400 text-sm">{formError}</p>}
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
          >
            Create task
          </button>
        </form>
      )}

      <div className="space-y-3">
        {tasks.map((t) => (
          <TaskCard key={t.id} task={t} onApprove={() => approve(t.id)} onRefresh={load} />
        ))}
        {tasks.length === 0 && (
          <p className="text-gray-500 text-sm">No tasks found.</p>
        )}
      </div>
    </div>
  );
}

function TaskCard({ task, onApprove, onRefresh }: { task: any; onApprove: () => void; onRefresh: () => void }) {
  const [runs, setRuns] = useState<any[]>([]);
  const [progress, setProgress] = useState<any[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [running, setRunning] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const isActive = task.status === "in_progress";
  const canRun = task.status === "approved" || task.status === "pending";
  const canRestart = task.status === "failed" || task.status === "cancelled" || task.status === "in_progress";

  const loadRuns = () => {
    api.listRuns(task.id).then((r) => {
      setRuns(r);
      // Load progress events for the latest run
      if (r.length > 0) {
        api.getRunProgress(r[0].id).then(setProgress).catch(() => {});
      }
      if (r.length > 0 && r[0].status !== "in_progress") {
        stopPolling();
        onRefresh();
      }
    }).catch(() => {});
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  useEffect(() => {
    if (isActive) {
      setExpanded(true);
      loadRuns();
      pollingRef.current = setInterval(loadRuns, 2000);
    }
    return () => stopPolling();
  }, [task.status]);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [progress]);

  const handleRun = async () => {
    setRunning(true);
    setExpanded(true);
    setProgress([]);
    try {
      if (canRestart) await api.resetTask(task.id);
      await api.runTask(task.id);
      onRefresh();
      loadRuns();
      pollingRef.current = setInterval(loadRuns, 2000);
    } catch (e) {
      setRunning(false);
    }
  };

  const toggleExpanded = () => {
    if (!expanded) loadRuns();
    setExpanded(!expanded);
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="p-5">
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <span className="text-white font-medium">
              #{task.issue_number} {task.issue_title}
            </span>
            <span className="ml-2 text-xs text-gray-500 font-mono">{task.id}</span>
          </div>
          <StatusBadge status={task.status} />
        </div>
        {task.issue_body && (
          <p className="text-sm text-gray-400 mb-3 line-clamp-2">{task.issue_body}</p>
        )}
        <div className="flex items-center gap-3 text-xs text-gray-500 flex-wrap">
          <span>{new Date(task.created_at).toLocaleString()}</span>

          <div className="ml-auto flex items-center gap-2">
            {task.status === "pending" && (
              <button
                onClick={onApprove}
                className="px-3 py-1 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg text-xs font-medium"
              >
                Approve
              </button>
            )}
            {canRun && (
              <button
                onClick={handleRun}
                disabled={running}
                className="px-3 py-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white rounded-lg text-xs font-medium"
              >
                {running ? "Starting..." : "Run"}
              </button>
            )}
            {canRestart && (
              <button
                onClick={handleRun}
                disabled={running}
                className="px-3 py-1 bg-orange-700 hover:bg-orange-600 disabled:opacity-50 text-white rounded-lg text-xs font-medium"
              >
                {running ? "Starting..." : "Restart"}
              </button>
            )}
            <button
              onClick={toggleExpanded}
              className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-xs font-medium"
            >
              {expanded ? "Hide" : "Details"}
            </button>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-800">
          {/* Live progress log */}
          {(isActive || progress.length > 0) && (
            <div className="px-5 pt-4 pb-2">
              <div className="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Pipeline log</div>
              <div
                ref={logRef}
                className="bg-gray-950 rounded-lg p-3 font-mono text-xs space-y-1 max-h-64 overflow-y-auto"
              >
                {progress.length === 0 && isActive && (
                  <div className="flex items-center gap-2 text-gray-400">
                    <Spinner /><span>Starting pipeline...</span>
                  </div>
                )}
                {progress.map((e, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-gray-600 shrink-0">
                      {new Date(e.ts * 1000).toLocaleTimeString()}
                    </span>
                    <span className={`shrink-0 w-20 ${agentColor(e.agent)}`}>[{e.agent}]</span>
                    <span className={levelColor(e.level)}>{e.message}</span>
                  </div>
                ))}
                {isActive && progress.length > 0 && (
                  <div className="flex items-center gap-2 text-gray-500">
                    <Spinner /><span>Running...</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Agent results — latest run only */}
          <div className="px-5 pb-4">
            {runs.length === 0 && !isActive ? (
              <p className="text-sm text-gray-500 pt-2">No runs yet.</p>
            ) : runs.length > 0 ? (
              <RunCard key={runs[0].id} run={runs[0]} />
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function RunCard({ run }: { run: any }) {
  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <StatusBadge status={run.status} />
        <span className="text-xs text-gray-500 font-mono">{run.id}</span>
        {run.branch_name && (
          <span className="text-xs text-gray-500 font-mono">{run.branch_name}</span>
        )}
        {run.pr_url && (
          <a
            href={run.pr_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs text-indigo-400 hover:text-indigo-300 font-medium"
          >
            View PR →
          </a>
        )}
      </div>

      {run.agent_results?.length > 0 && (
        <div className="space-y-1">
          {run.agent_results.map((r: any, i: number) => (
            <AgentResultRow key={i} r={r} />
          ))}
        </div>
      )}

      {run.status === "in_progress" && (run.agent_results?.length ?? 0) === 0 && (
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Spinner />
          Pipeline is running...
        </div>
      )}
    </div>
  );
}

function AgentResultRow({ r }: { r: any }) {
  const [open, setOpen] = useState(false);
  const output = r.output ?? {};
  const hasArtifact = Object.keys(output).some(
    (k) => !["session_id", "num_turns", "cost_usd", "raw"].includes(k)
  ) || output.raw;

  const inlineSummary = () => {
    if (r.role === "planner" && output.summary)
      return <span className="text-xs text-gray-400 truncate max-w-xs hidden sm:inline">{output.summary}</span>;
    if (r.role === "reviewer" && output.approved !== undefined) {
      const crits = (output.issues ?? []).filter((i: any) => i.severity === "critical").length;
      return output.approved
        ? <span className="text-xs text-green-400">Approved</span>
        : <span className="text-xs text-red-400">{crits} critical issue{crits !== 1 ? "s" : ""}</span>;
    }
    if (r.role === "developer" && output.num_turns)
      return <span className="text-xs text-gray-400">{output.num_turns} turns</span>;
    return null;
  };

  return (
    <div className="bg-gray-800/60 rounded-lg overflow-hidden">
      <button
        onClick={() => hasArtifact && setOpen(!open)}
        className={`w-full px-4 py-2 flex items-center justify-between text-left ${hasArtifact ? "cursor-pointer hover:bg-gray-800" : "cursor-default"}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <AgentIcon role={r.role} />
          <span className="text-sm font-medium text-white capitalize shrink-0">{r.role}</span>
          {inlineSummary()}
          {r.error && <span className="text-xs text-red-400 truncate">{r.error}</span>}
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500 shrink-0 ml-2">
          {output.cost_usd > 0 && <span className="text-gray-600">${output.cost_usd.toFixed(3)}</span>}
          {r.duration_ms > 0 && <span>{(r.duration_ms / 1000).toFixed(1)}s</span>}
          {r.tokens_used > 0 && <span>{r.tokens_used.toLocaleString()} tok</span>}
          <span className={r.success ? "text-green-400 font-medium" : "text-red-400 font-medium"}>
            {r.success ? "✓" : "✗"}
          </span>
          {hasArtifact && (
            <span className="text-gray-600 text-base leading-none">{open ? "▲" : "▼"}</span>
          )}
        </div>
      </button>

      {open && hasArtifact && (
        <div className="border-t border-gray-700/40 px-4 pt-3 pb-4">
          <ArtifactPanel role={r.role} output={output} />
        </div>
      )}
    </div>
  );
}

function ArtifactPanel({ role, output }: { role: string; output: any }) {
  if (role === "planner") return <PlannerArtifact output={output} />;
  if (role === "reviewer") return <ReviewerArtifact output={output} />;
  if (role === "tester") return <TesterArtifact output={output} />;
  if (role === "developer") return <DeveloperArtifact output={output} />;
  return <pre className="text-xs text-gray-400 whitespace-pre-wrap">{JSON.stringify(output, null, 2)}</pre>;
}

function PlannerArtifact({ output }: { output: any }) {
  const complexityColor: Record<string, string> = {
    low: "bg-green-400/10 text-green-400",
    medium: "bg-yellow-400/10 text-yellow-400",
    high: "bg-red-400/10 text-red-400",
  };
  return (
    <div className="space-y-3 text-sm">
      {output.summary && (
        <p className="text-gray-200">{output.summary}</p>
      )}
      <div className="flex items-center gap-3 flex-wrap">
        {output.estimated_complexity && (
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${complexityColor[output.estimated_complexity] ?? "bg-gray-700 text-gray-300"}`}>
            complexity: {output.estimated_complexity}
          </span>
        )}
        {output.num_turns && (
          <span className="text-xs text-gray-500">{output.num_turns} turns</span>
        )}
      </div>
      {output.steps?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Steps</p>
          <ol className="space-y-1">
            {output.steps.map((s: any, i: number) => (
              <li key={i} className="flex gap-2">
                <span className="text-gray-600 shrink-0 w-5 text-right">{i + 1}.</span>
                <div>
                  <span className="text-gray-200">{s.description}</span>
                  {s.files?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {s.files.map((f: string, j: number) => (
                        <span key={j} className="text-xs font-mono text-indigo-300 bg-indigo-900/30 px-1.5 rounded">
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
      {output.dependencies?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Dependencies</p>
          <div className="flex flex-wrap gap-1">
            {output.dependencies.map((d: string, i: number) => (
              <span key={i} className="text-xs font-mono bg-gray-700 text-gray-200 px-2 py-0.5 rounded">{d}</span>
            ))}
          </div>
        </div>
      )}
      {output.risks?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Risks</p>
          <ul className="space-y-0.5">
            {output.risks.map((r: string, i: number) => (
              <li key={i} className="text-xs text-yellow-300/80">⚠ {r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ReviewerArtifact({ output }: { output: any }) {
  const sevColor: Record<string, string> = {
    critical: "bg-red-400/10 text-red-400 border-red-400/20",
    warning: "bg-yellow-400/10 text-yellow-300 border-yellow-400/20",
    suggestion: "bg-blue-400/10 text-blue-300 border-blue-400/20",
  };
  const issues: any[] = output.issues ?? [];
  return (
    <div className="space-y-3 text-sm">
      {output.summary && (
        <p className="text-gray-200">{output.summary}</p>
      )}
      {issues.length === 0 ? (
        <p className="text-xs text-green-400">No issues found.</p>
      ) : (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Issues ({issues.length})
          </p>
          <div className="space-y-2">
            {issues.map((issue: any, i: number) => (
              <div key={i} className={`rounded-lg border px-3 py-2 ${sevColor[issue.severity] ?? "bg-gray-700/30 text-gray-300 border-gray-600"}`}>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-medium uppercase">{issue.severity}</span>
                  {issue.file && (
                    <span className="text-xs font-mono opacity-70">{issue.file}</span>
                  )}
                </div>
                <p className="text-xs">{issue.description}</p>
                {issue.fix_suggestion && (
                  <p className="text-xs opacity-70 mt-1">→ {issue.fix_suggestion}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {output.num_turns && (
        <p className="text-xs text-gray-600">{output.num_turns} turns</p>
      )}
    </div>
  );
}

function TesterArtifact({ output }: { output: any }) {
  const files: any[] = output.test_files ?? [];
  return (
    <div className="space-y-3 text-sm">
      {output.summary && <p className="text-gray-200">{output.summary}</p>}
      {output.raw && !output.summary && (
        <pre className="text-xs text-gray-300 whitespace-pre-wrap bg-gray-900 rounded p-2 max-h-48 overflow-y-auto">
          {output.raw}
        </pre>
      )}
      {files.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Test files created</p>
          <div className="space-y-1">
            {files.map((f: any, i: number) => (
              <span key={i} className="block text-xs font-mono text-indigo-300 bg-indigo-900/30 px-2 py-0.5 rounded">
                + {f.path}
              </span>
            ))}
          </div>
        </div>
      )}
      {output.num_turns && (
        <p className="text-xs text-gray-600">{output.num_turns} turns</p>
      )}
    </div>
  );
}

function DeveloperArtifact({ output }: { output: any }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap gap-4 text-xs text-gray-400">
        {output.num_turns && <span><span className="text-gray-600">turns</span> {output.num_turns}</span>}
        {output.cost_usd > 0 && <span><span className="text-gray-600">cost</span> ${output.cost_usd.toFixed(4)}</span>}
        {output.session_id && (
          <span className="font-mono"><span className="text-gray-600">session</span> {output.session_id.slice(0, 12)}…</span>
        )}
      </div>
      <p className="text-xs text-gray-500">File changes are visible in the git diff / PR.</p>
    </div>
  );
}

function agentColor(agent: string): string {
  const map: Record<string, string> = {
    planner: "text-blue-400",
    developer: "text-green-400",
    reviewer: "text-purple-400",
    tester: "text-yellow-400",
    orchestrator: "text-gray-400",
  };
  return map[agent] ?? "text-gray-400";
}

function levelColor(level: string): string {
  const map: Record<string, string> = {
    success: "text-green-400",
    warning: "text-yellow-400",
    error: "text-red-400",
    info: "text-gray-300",
  };
  return map[level] ?? "text-gray-300";
}

function AgentIcon({ role }: { role: string }) {
  const icons: Record<string, string> = {
    planner: "🗺️",
    developer: "💻",
    reviewer: "🔍",
    tester: "🧪",
  };
  return <span>{icons[role] ?? "🤖"}</span>;
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-indigo-400" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-yellow-400/10 text-yellow-400",
    approved: "bg-blue-400/10 text-blue-400",
    in_progress: "bg-indigo-400/10 text-indigo-400",
    review: "bg-purple-400/10 text-purple-400",
    completed: "bg-green-400/10 text-green-400",
    failed: "bg-red-400/10 text-red-400",
    cancelled: "bg-gray-700 text-gray-400",
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-700 text-gray-300"}`}>
      {status}
    </span>
  );
}
