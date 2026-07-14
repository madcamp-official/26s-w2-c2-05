const API_BASE = "http://localhost:8000";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export type Project = {
  id: string;
  name: string;
  content: string;
  hooks_content: string;
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

export type OnboardingRequest = {
  principles: string[];
  tech_stack: string;
  team_or_individual: "team" | "individual";
  indent_style: "tabs" | "spaces";
  custom_requirements?: string;
};

export async function onboardProject(id: string, req: OnboardingRequest): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}/onboarding`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "온보딩 생성에 실패했습니다");
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

export async function saveProjectHooks(id: string, hooksContent: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}/hooks`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ hooks_content: hooksContent }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "저장에 실패했습니다");
  }
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
  target: "content" | "hooks";
};

export type RevisionDetail = Revision & {
  content: string;
};

export async function listRevisions(
  id: string,
  target?: "content" | "hooks"
): Promise<Revision[]> {
  const query = target ? `?target=${target}` : "";
  const res = await fetch(`${API_BASE}/projects/${id}/revisions${query}`, {
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

export type HookPayload = {
  event: string;
  matcher: string;
  command: string;
  reason: string;
  confidence: "low" | "medium" | "high";
};

export type ClaudeMdPayload = {
  suggested_text: string;
  reason: string;
  confidence: "low" | "medium" | "high";
};

export type SkillPayload = {
  skill_name: string;
  skill_description: string;
  suggested_steps: string;
  reason: string;
  confidence: "low" | "medium" | "high";
};

export type PersonalRecommendation = {
  id: string;
  type: "hook" | "claude_md" | "skill";
  payload: HookPayload | ClaudeMdPayload | SkillPayload;
  applied: boolean;
};

export type TeamGroupUpdate = {
  id: string;
  type: "hook" | "claude_md";
  representative_text: string;
  affected_members: number;
  promoted: boolean;
};

export type UploadSessionResult = {
  session_id: string;
  status: "processed" | "no_patterns";
  personal_recommendations: PersonalRecommendation[];
  updated_team_groups: TeamGroupUpdate[];
};

export async function uploadSession(id: string, file: File): Promise<UploadSessionResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/projects/${id}/sessions`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "세션 업로드에 실패했습니다");
  }
  return res.json();
}

export async function getMyRecommendations(id: string): Promise<PersonalRecommendation[]> {
  const res = await fetch(`${API_BASE}/projects/${id}/recommendations/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("내 추천을 불러오지 못했습니다");
  return res.json();
}

export type TeamRecommendation = {
  id: string;
  type: "hook" | "claude_md" | "skill";
  representative_text: string;
  affected_members: number;
  applied: boolean;
  evidence: { user_id: number; original_text: string }[];
  event: string | null;
  matcher: string | null;
};

export async function getTeamRecommendations(id: string): Promise<TeamRecommendation[]> {
  const res = await fetch(`${API_BASE}/projects/${id}/recommendations/team`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("팀 추천을 불러오지 못했습니다");
  return res.json();
}

export async function applyRecommendationGroup(id: string, groupId: string): Promise<void> {
  const res = await fetch(
    `${API_BASE}/projects/${id}/recommendation-groups/${groupId}/apply`,
    { method: "POST", headers: authHeaders() }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "추천 적용에 실패했습니다");
  }
}

export async function applyPersonalRecommendationApi(
  id: string,
  recommendationId: string
): Promise<void> {
  const res = await fetch(
    `${API_BASE}/projects/${id}/personal-recommendations/${recommendationId}/apply`,
    { method: "POST", headers: authHeaders() }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "추천 적용에 실패했습니다");
  }
}

export type Skill = {
  id: string;
  name: string;
  description: string;
  steps_content: string;
  created_at: string;
  updated_at: string;
};

export async function listSkills(id: string): Promise<Skill[]> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("스킬 목록을 불러오지 못했습니다");
  return res.json();
}

export async function getSkill(id: string, skillId: string): Promise<Skill> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills/${skillId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("스킬을 찾을 수 없습니다");
  return res.json();
}

export async function saveSkill(
  id: string,
  skillId: string,
  data: { name: string; description: string; steps_content: string }
): Promise<Skill> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills/${skillId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "스킬 저장에 실패했습니다");
  }
  return res.json();
}

export async function deleteSkill(id: string, skillId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}/skills/${skillId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? "스킬 삭제에 실패했습니다");
  }
}
