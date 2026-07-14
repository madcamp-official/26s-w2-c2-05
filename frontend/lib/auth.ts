const API_BASE = "/api";

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export async function signup(username: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "회원가입에 실패했습니다");
  }
  return res.json();
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "로그인에 실패했습니다");
  }
  return res.json();
}

export function logout(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("username");
}

export async function connectGithub(): Promise<void> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}/auth/github/login`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("GitHub 연결을 시작하지 못했습니다");
  const { authorize_url } = await res.json();
  window.location.href = authorize_url;
}

export async function getGithubStatus(): Promise<{ connected: boolean; username: string | null }> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}/auth/github/status`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("GitHub 연결 상태를 확인하지 못했습니다");
  return res.json();
}

export async function disconnectGithub(): Promise<void> {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}/auth/github/disconnect`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("GitHub 연결 해제에 실패했습니다");
}
