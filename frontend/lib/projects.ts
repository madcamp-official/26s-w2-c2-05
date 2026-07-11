export type ProjectMeta = {
  id: string;
  name: string;
  createdAt: string;
};

const PROJECTS_KEY = "projects";

function projectContentKey(id: string): string {
  return `project-md-${id}`;
}

export function listProjects(): ProjectMeta[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(PROJECTS_KEY);
  return raw ? (JSON.parse(raw) as ProjectMeta[]) : [];
}

export function getProject(id: string): ProjectMeta | undefined {
  return listProjects().find((project) => project.id === id);
}

export function createProject(name: string): ProjectMeta {
  const project: ProjectMeta = {
    id: crypto.randomUUID(),
    name,
    createdAt: new Date().toISOString(),
  };
  localStorage.setItem(PROJECTS_KEY, JSON.stringify([...listProjects(), project]));
  return project;
}

export function getProjectContent(id: string): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(projectContentKey(id)) ?? "";
}

export function saveProjectContent(id: string, content: string): void {
  localStorage.setItem(projectContentKey(id), content);
}
