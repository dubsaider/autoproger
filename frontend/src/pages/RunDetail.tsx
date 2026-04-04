import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    if (!runId) return;
    api.getRun(runId).then(setRun).catch(() => {
      api.listRuns(runId).then(setRuns).catch(() => {});
    });
  }, [runId]);

  if (runs.length > 0) {
    return (
      <div>
        <h2 className="text-2xl font-bold text-white mb-6">Runs for task {runId}</h2>
        <div className="space-y-3">
          {runs.map((r) => (
            <div key={r.id} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-white font-mono text-sm">{r.id}</span>
                <StatusBadge status={r.status} />
              </div>
              {r.pr_url && (
                <a href={r.pr_url} target="_blank" className="text-indigo-400 text-sm hover:underline">
                  View PR
                </a>
              )}
              <AgentResults results={r.agent_results || []} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!run) {
    return <p className="text-gray-500">Loading...</p>;
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-2">Run {run.id}</h2>
      <div className="flex items-center gap-3 mb-6">
        <StatusBadge status={run.status} />
        <span className="text-sm text-gray-500">Task: {run.task_id}</span>
        {run.branch_name && (
          <span className="text-sm text-gray-500">Branch: {run.branch_name}</span>
        )}
        {run.pr_url && (
          <a href={run.pr_url} target="_blank" className="text-sm text-indigo-400 hover:underline">
            View PR
          </a>
        )}
      </div>

      <AgentResults results={run.agent_results || []} />
    </div>
  );
}

function AgentResults({ results }: { results: any[] }) {
  if (results.length === 0) return null;
  return (
    <div className="mt-4 space-y-2">
      <h3 className="text-sm font-semibold text-gray-300">Agent pipeline</h3>
      {results.map((r, i) => (
        <div
          key={i}
          className="bg-gray-800/50 rounded-lg p-3 flex items-center justify-between"
        >
          <div>
            <span className="text-sm font-medium text-white capitalize">{r.role}</span>
            {r.error && <span className="ml-2 text-xs text-red-400">{r.error}</span>}
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span>{r.duration_ms}ms</span>
            <span>{r.tokens_used} tokens</span>
            <span className={r.success ? "text-green-400" : "text-red-400"}>
              {r.success ? "OK" : "FAIL"}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-yellow-400/10 text-yellow-400",
    in_progress: "bg-blue-400/10 text-blue-400",
    completed: "bg-green-400/10 text-green-400",
    failed: "bg-red-400/10 text-red-400",
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${map[status] ?? "bg-gray-700 text-gray-300"}`}>
      {status}
    </span>
  );
}
