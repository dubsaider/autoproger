const API = '/api';

function getToken(): string | null {
  return localStorage.getItem('token');
}

export async function login(username: string, password: string): Promise<{ access_token: string }> {
  const res = await fetch(`${API}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || 'Ошибка входа');
  }
  return res.json();
}

export async function me(): Promise<{ username: string }> {
  const token = getToken();
  if (!token) throw new Error('Нет токена');
  const res = await fetch(`${API}/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Не авторизован');
  return res.json();
}

export interface RepoItem {
  id: string | number;
  name: string;
  path_with_namespace?: string;
  web_url?: string;
}

export interface ConnectionConfig {
  provider: 'github' | 'gitlab';
  gitlab_url: string;
  gitlab_token: string;
  selected_projects: RepoItem[];
  github_token: string;
  selected_repos: RepoItem[];
  repo_path_base: string;
  git_author_name: string;
  git_author_email: string;
  create_draft_mr: boolean;
  issue_labels: string[];
  llm_provider: string;
  anthropic_api_key: string;
  claude_model: string;
  cursor_cli_cmd: string;
  cursor_timeout_sec: number;
  actuality_check_llm: boolean;
}

export async function getConfig(): Promise<{ config: ConnectionConfig }> {
  const token = getToken();
  if (!token) throw new Error('Нет токена');
  const res = await fetch(`${API}/config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Ошибка загрузки конфига');
  return res.json();
}

export interface IssueItem {
  number: number
  title: string
  body: string
  labels: string[]
  state: string
  html_url: string
}

export interface IssueDraft {
  title: string
  body: string
  labels: string[]
  repo: string
}

export interface ProblemFinding {
  severity: 'low' | 'medium' | 'high' | 'critical' | string
  title: string
  file: string
  description: string
  hint: string
}

export interface RepoCloneItem {
  repo: string
  local_path: string
  status: 'cloned' | 'pulled' | 'exists' | 'error' | string
  message: string
}

export async function getIssues(repo?: string, labels?: string): Promise<{
  repo: string
  issues: IssueItem[]
}> {
  const token = getToken()
  if (!token) throw new Error('Нет токена')
  const params = new URLSearchParams()
  if (repo) params.set('repo', repo)
  if (labels) params.set('labels', labels)
  const q = params.toString()
  const res = await fetch(`${API}/issues${q ? `?${q}` : ''}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || 'Ошибка загрузки issues')
  }
  return res.json()
}

export async function draftIssue(brief: string, repo?: string): Promise<IssueDraft> {
  const token = getToken()
  if (!token) throw new Error('Нет токена')
  const res = await fetch(`${API}/issues/draft`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ brief, repo }),
  })
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || 'Ошибка генерации issue')
  }
  return res.json()
}

export async function createIssue(payload: {
  title: string
  body: string
  labels: string[]
  repo?: string
}): Promise<{ number: number; title: string; html_url: string; repo: string }> {
  const token = getToken()
  if (!token) throw new Error('Нет токена')
  const res = await fetch(`${API}/issues/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || 'Ошибка создания issue')
  }
  return res.json()
}

export async function scanProblems(payload: {
  repo?: string
  run_tests?: boolean
}): Promise<{ repo: string; findings: ProblemFinding[] }> {
  const token = getToken()
  if (!token) throw new Error('Нет токена')
  const res = await fetch(`${API}/problems/scan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || 'Ошибка поиска проблем')
  }
  return res.json()
}

export async function cloneRepos(payload: {
  repo?: string
  clone_all?: boolean
  pull_if_exists?: boolean
}): Promise<{ results: RepoCloneItem[] }> {
  const token = getToken()
  if (!token) throw new Error('Нет токена')
  const res = await fetch(`${API}/repos/clone`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || 'Ошибка клонирования репозитория')
  }
  return res.json()
}

/** Сводка без секретов: что реально используется при запуске пайплайна */
export interface ConfigSummary {
  ok: boolean;
  source?: 'admin' | 'env';
  provider?: string;
  repos?: Array<{ path_with_namespace: string; name: string }>;
  repo_path_base?: string;
  error?: string;
}

export async function getConfigSummary(): Promise<ConfigSummary> {
  const token = getToken();
  if (!token) throw new Error('Нет токена');
  const res = await fetch(`${API}/config/summary`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Ошибка загрузки');
  return res.json();
}

export async function saveConfig(config: ConnectionConfig): Promise<{ config: ConnectionConfig }> {
  const token = getToken();
  if (!token) throw new Error('Нет токена');
  const res = await fetch(`${API}/config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ config }),
  });
  if (!res.ok) throw new Error('Ошибка сохранения');
  return res.json();
}

export async function fetchGitLabProjects(
  gitlab_url: string,
  token: string,
  search: string = ''
): Promise<{ projects: Array<{ id: number; path_with_namespace: string; name: string; web_url: string }> }> {
  const authToken = getToken();
  if (!authToken) throw new Error('Нет токена');
  const res = await fetch(`${API}/gitlab/projects`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ gitlab_url, token, search }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || 'Ошибка загрузки проектов');
  }
  return res.json();
}

export async function fetchGitHubRepos(
  token: string,
  search: string = ''
): Promise<{ repos: Array<{ id: string; path_with_namespace: string; name: string; web_url: string }> }> {
  const authToken = getToken();
  if (!authToken) throw new Error('Нет токена');
  const res = await fetch(`${API}/github/repos`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify({ token, search }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || 'Ошибка загрузки репозиториев');
  }
  return res.json();
}
