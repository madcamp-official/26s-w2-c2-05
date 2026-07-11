const API_BASE = "http://localhost:8000";

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
}
