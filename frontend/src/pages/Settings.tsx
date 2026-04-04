import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Settings() {
  const [config, setConfig] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => {});
  }, []);

  const save = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const updated = await api.updateConfig(config);
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (!config) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-6">Settings</h2>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-xl space-y-4">
        <label className="block">
          <span className="text-sm text-gray-400">LLM Provider</span>
          <select
            value={config.llm_default_provider}
            onChange={(e) => setConfig({ ...config, llm_default_provider: e.target.value })}
            className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
          >
            <option value="claude_code">Claude Code CLI (primary)</option>
            <option value="anthropic">Anthropic API (fallback)</option>
            <option value="openrouter">OpenRouter (fallback)</option>
          </select>
        </label>

        <label className="block">
          <span className="text-sm text-gray-400">Model</span>
          <input
            type="text"
            value={config.llm_default_model}
            onChange={(e) => setConfig({ ...config, llm_default_model: e.target.value })}
            className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
          />
        </label>

        <label className="block">
          <span className="text-sm text-gray-400">Log level</span>
          <select
            value={config.log_level}
            onChange={(e) => setConfig({ ...config, log_level: e.target.value })}
            className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
          >
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </label>

        <div className="flex items-center gap-3">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          {saved && <span className="text-green-400 text-sm">Saved!</span>}
        </div>
      </div>
    </div>
  );
}
