const API_BASE = "http://localhost:8000";

export type Project = {
  id: string;
  name: string;
  content: string;
  created_at: string;
};

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`);
  if (!res.ok) throw new Error("프로젝트 목록을 불러오지 못했습니다");
  return res.json();
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}`);
  if (!res.ok) throw new Error("프로젝트를 찾을 수 없습니다");
  return res.json();
}

export async function createProject(name: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("프로젝트 생성에 실패했습니다");
  return res.json();
}

export async function saveProjectContent(id: string, content: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error("저장에 실패했습니다");
  return res.json();
}
