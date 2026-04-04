import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [filter, setFilter] = useState("");

  const load = () => {
    const params: Record<string, string> = {};
    if (filter) params.status = filter;
    api.listTasks(params).then(setTasks).catch(() => {});
  };

  useEffect(() => { load(); }, [filter]);

  const approve = async (id: string) => {
    await api.approveTask(id);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Tasks</h2>
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
      </div>

      <div className="space-y-3">
        {tasks.map((t) => (
          <div
            key={t.id}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-white font-medium">
                  #{t.issue_number} {t.issue_title}
                </span>
                <span className="ml-2 text-xs text-gray-500 font-mono">{t.id}</span>
              </div>
              <StatusBadge status={t.status} />
            </div>
            {t.issue_body && (
              <p className="text-sm text-gray-400 mb-3 line-clamp-2">{t.issue_body}</p>
            )}
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span>Repo: {t.repo_id}</span>
              <span>{new Date(t.created_at).toLocaleString()}</span>
              {t.status === "pending" && (
                <button
                  onClick={() => approve(t.id)}
                  className="ml-auto px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium"
                >
                  Approve
                </button>
              )}
              <Link
                to={`/runs/${t.id}`}
                className="text-indigo-400 hover:text-indigo-300"
              >
                View runs
              </Link>
            </div>
          </div>
        ))}
        {tasks.length === 0 && (
          <p className="text-gray-500 text-sm">No tasks found.</p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-yellow-400/10 text-yellow-400",
    approved: "bg-blue-400/10 text-blue-400",
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
