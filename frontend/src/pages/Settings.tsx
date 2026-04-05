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

  const set = (key: string, value: any) => setConfig((c: any) => ({ ...c, [key]: value }));

  if (!config) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-2xl font-bold text-white">Settings</h2>

      {/* LLM */}
      <Section title="LLM Provider">
        <Field label="Provider">
          <select
            value={config.llm_default_provider}
            onChange={(e) => set("llm_default_provider", e.target.value)}
            className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
          >
            <option value="claude_code">Claude Code CLI (primary)</option>
            <option value="anthropic">Anthropic API (fallback)</option>
            <option value="openrouter">OpenRouter (fallback)</option>
          </select>
        </Field>
        <Field label="Model">
          <input
            type="text"
            value={config.llm_default_model}
            onChange={(e) => set("llm_default_model", e.target.value)}
            className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
          />
        </Field>
        <Field label="Log level">
          <select
            value={config.log_level}
            onChange={(e) => set("log_level", e.target.value)}
            className="mt-1 w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white"
          >
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </Field>
      </Section>

      {/* Token budget */}
      <Section
        title="Token Budget"
        hint="Limit how many turns and how much money each agent can spend per run. 0 = unlimited."
      >
        <div className="grid grid-cols-[1fr_80px_100px] gap-x-4 gap-y-3 items-end">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Agent</div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Max turns</div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Budget USD</div>

          {(
            [
              { label: "🗺️ Planner", turns: "claude_code_max_turns_planner", budget: "claude_code_budget_planner" },
              { label: "💻 Developer", turns: "claude_code_max_turns_developer", budget: "claude_code_budget_developer" },
              { label: "🔍 Reviewer", turns: "claude_code_max_turns_reviewer", budget: "claude_code_budget_reviewer" },
              { label: "🧪 Tester", turns: "claude_code_max_turns_tester", budget: "claude_code_budget_tester" },
            ] as const
          ).map(({ label, turns, budget }) => (
            <>
              <span key={label} className="text-sm text-gray-300">{label}</span>
              <input
                type="number"
                min={0}
                max={50}
                value={config[turns]}
                onChange={(e) => set(turns, parseInt(e.target.value, 10) || 0)}
                className="px-2 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm text-center"
              />
              <div className="relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={config[budget]}
                  onChange={(e) => set(budget, parseFloat(e.target.value) || 0)}
                  className="w-full pl-6 pr-2 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
                />
              </div>
            </>
          ))}
        </div>

        <p className="text-xs text-gray-600 mt-3">
          💡 Suggested starting values: Planner 12 turns / $0.50 · Developer 10 / $1.00 · Reviewer 6 / $0.30 · Tester 8 / $0.50
        </p>
      </Section>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
        >
          {saving ? "Saving..." : "Save settings"}
        </button>
        {saved && <span className="text-green-400 text-sm">✓ Saved</span>}
      </div>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
      <div>
        <h3 className="text-white font-semibold">{title}</h3>
        {hint && <p className="text-xs text-gray-500 mt-0.5">{hint}</p>}
      </div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm text-gray-400">{label}</span>
      {children}
    </label>
  );
}
