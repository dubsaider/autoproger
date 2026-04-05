const BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  listRepos: () => request<any[]>("/repos"),
  createRepo: (data: any) =>
    request<any>("/repos", { method: "POST", body: JSON.stringify(data) }),
  deleteRepo: (id: string) =>
    request<void>(`/repos/${id}`, { method: "DELETE" }),

  listTasks: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<any[]>(`/tasks${qs}`);
  },
  getTask: (id: string) => request<any>(`/tasks/${id}`),
  createTask: (data: { repo_id: string; issue_title: string; issue_body?: string }) =>
    request<any>("/tasks/create", { method: "POST", body: JSON.stringify(data) }),
  runTask: (taskId: string) =>
    request<any>(`/tasks/${taskId}/run`, { method: "POST" }),
  resetTask: (taskId: string) =>
    request<any>(`/tasks/${taskId}/reset`, { method: "POST" }),
  getRunProgress: (runId: string) =>
    request<any[]>(`/runs/${runId}/progress`),
  approveTask: (taskId: string) =>
    request<any>("/tasks/approve", {
      method: "POST",
      body: JSON.stringify({ task_id: taskId }),
    }),

  listRuns: (taskId?: string) => {
    const qs = taskId ? `?task_id=${taskId}` : "";
    return request<any[]>(`/runs${qs}`);
  },
  getRun: (id: string) => request<any>(`/runs/${id}`),

  getConfig: () => request<any>("/config"),
  updateConfig: (data: any) =>
    request<any>("/config", { method: "PATCH", body: JSON.stringify(data) }),
};
