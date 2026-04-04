import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function Dashboard() {
  const [repos, setRepos] = useState<any[]>([]);
  const [tasks, setTasks] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    api.listRepos().then(setRepos).catch(() => {});
    api.listTasks().then(setTasks).catch(() => {});
    api.listRuns().then(setRuns).catch(() => {});
  }, []);

  const pending = tasks.filter((t) => t.status === "pending").length;
  const inProgress = tasks.filter((t) => t.status === "in_progress").length;
  const completed = tasks.filter((t) => t.status === "completed").length;

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Repositories" value={repos.length} color="indigo" />
        <StatCard label="Pending" value={pending} color="yellow" />
        <StatCard label="In progress" value={inProgress} color="blue" />
        <StatCard label="Completed" value={completed} color="green" />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="font-semibold text-white">Recent runs</h3>
          <Link to="/tasks" className="text-sm text-indigo-400 hover:text-indigo-300">
            View all tasks
          </Link>
        </div>
        {runs.length === 0 ? (
          <p className="p-5 text-gray-500 text-sm">No runs yet</p>
        ) : (
          <div className="divide-y divide-gray-800">
            {runs.slice(0, 10).map((r) => (
              <Link
                key={r.id}
                to={`/runs/${r.id}`}
                className="flex items-center justify-between px-5 py-3 hover:bg-gray-800/50 transition-colors"
              >
                <div>
                  <span className="text-sm text-white font-mono">{r.id}</span>
                  <span className="ml-3 text-xs text-gray-500">task {r.task_id}</span>
                </div>
                <StatusBadge status={r.status} />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const colors: Record<string, string> = {
    indigo: "text-indigo-400 bg-indigo-400/10",
    yellow: "text-yellow-400 bg-yellow-400/10",
    blue: "text-blue-400 bg-blue-400/10",
    green: "text-green-400 bg-green-400/10",
  };
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-sm text-gray-400 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${colors[color]?.split(" ")[0] ?? "text-white"}`}>
        {value}
      </p>
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
