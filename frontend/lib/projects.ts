const API_BASE = "http://localhost:8000";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export type Project = {
  id: string;
  name: string;
  content: string;
  github_repo: string | null;
  created_at: string;
  role: "owner" | "member";
};

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`, { headers: authHeaders() });
  if (!res.ok) throw new Error("프로젝트 목록을 불러오지 못했습니다");
  return res.json();
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("프로젝트를 찾을 수 없습니다");
  return res.json();
}

export async function createProject(name: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("프로젝트 생성에 실패했습니다");
  return res.json();
}

export async function renameProject(id: string, name: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}/name`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "이름 수정에 실패했습니다");
  }
  return res.json();
}

export async function saveProjectContent(id: string, content: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("저장에 실패했습니다");
  return res.json();
}

export async function setGithubRepo(id: string, repo: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}/github`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ repo }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "repo 설정에 실패했습니다");
  }
  return res.json();
}

export async function inviteMember(id: string, username: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}/invite`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ username }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "초대에 실패했습니다");
  }
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "프로젝트 삭제에 실패했습니다");
  }
}

export async function pushToGithub(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}/push`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "push에 실패했습니다");
  }
}

export type Revision = {
  id: string;
  created_at: string;
  username: string;
};

export type RevisionDetail = Revision & {
  content: string;
};

export async function listRevisions(id: string): Promise<Revision[]> {
  const res = await fetch(`${API_BASE}/projects/${id}/revisions`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("변경 이력을 불러오지 못했습니다");
  return res.json();
}

export async function getRevision(id: string, revisionId: string): Promise<RevisionDetail> {
  const res = await fetch(`${API_BASE}/projects/${id}/revisions/${revisionId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("변경 이력을 불러오지 못했습니다");
  return res.json();
}
