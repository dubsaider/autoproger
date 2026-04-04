import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Repos() {
  const [repos, setRepos] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    platform: "github",
    url: "",
    token: "",
    autonomy: "semi_auto",
    default_branch: "main",
    watch_labels: "autoproger",
  });

  const load = () => api.listRepos().then(setRepos).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.createRepo({
      ...form,
      watch_labels: form.watch_labels.split(",").map((l) => l.trim()),
    });
    setShowForm(false);
    setForm({ platform: "github", url: "", token: "", autonomy: "semi_auto", default_branch: "main", watch_labels: "autoproger" });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this repository?")) return;
    await api.deleteRepo(id);
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Repositories</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {showForm ? "Cancel" : "Add repo"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block">
              <span className="text-sm text-gray-400">Platform</span>
              <select
                value={form.platform}
                onChange={(e) => setForm({ ...form, platform: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              >
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm text-gray-400">Repository URL</span>
              <input
                type="text"
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://github.com/owner/repo"
                className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                required
              />
            </label>
            <label className="block">
              <span className="text-sm text-gray-400">Access token</span>
              <input
                type="password"
                value={form.token}
                onChange={(e) => setForm({ ...form, token: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
                required
              />
            </label>
            <label className="block">
              <span className="text-sm text-gray-400">Autonomy</span>
              <select
                value={form.autonomy}
                onChange={(e) => setForm({ ...form, autonomy: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              >
                <option value="full_auto">Full auto</option>
                <option value="semi_auto">Semi auto</option>
                <option value="manual">Manual</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm text-gray-400">Default branch</span>
              <input
                type="text"
                value={form.default_branch}
                onChange={(e) => setForm({ ...form, default_branch: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              />
            </label>
            <label className="block">
              <span className="text-sm text-gray-400">Watch labels (comma-separated)</span>
              <input
                type="text"
                value={form.watch_labels}
                onChange={(e) => setForm({ ...form, watch_labels: e.target.value })}
                className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
              />
            </label>
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium"
          >
            Add repository
          </button>
        </form>
      )}

      <div className="space-y-3">
        {repos.map((r) => (
          <div
            key={r.id}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between"
          >
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="px-2 py-0.5 text-xs font-medium rounded bg-gray-800 text-gray-300 uppercase">
                  {r.platform}
                </span>
                <span className="text-white font-medium">{r.url}</span>
              </div>
              <div className="text-xs text-gray-500 space-x-4">
                <span>Autonomy: {r.autonomy}</span>
                <span>Branch: {r.default_branch}</span>
                <span>Labels: {(r.watch_labels || []).join(", ")}</span>
              </div>
            </div>
            <button
              onClick={() => handleDelete(r.id)}
              className="text-sm text-red-400 hover:text-red-300"
            >
              Delete
            </button>
          </div>
        ))}
        {repos.length === 0 && (
          <p className="text-gray-500 text-sm">No repositories configured yet.</p>
        )}
      </div>
    </div>
  );
}
