"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { listProjects, deleteProject, type Project } from "@/lib/projects";
import { connectGithub, disconnectGithub, getGithubStatus } from "@/lib/auth";

export default function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [username, setUsername] = useState("");
  const [githubConnected, setGithubConnected] = useState(false);
  const [githubUsername, setGithubUsername] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pathname = usePathname();

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, [pathname]);

  useEffect(() => {
    setUsername(localStorage.getItem("username") ?? "");
    getGithubStatus()
      .then((s) => {
        setGithubConnected(s.connected);
        setGithubUsername(s.username);
      })
      .catch(() => setGithubConnected(false));
  }, [pathname]);

  if (pathname === "/login" || pathname === "/signup" || pathname === "/fund") return null;

  const ownedProjects = projects.filter((p) => p.role === "owner");
  const memberProjects = projects.filter((p) => p.role !== "owner");

  async function handleDeleteProject(projectId: string) {
    if (!confirm("이 프로젝트를 삭제할까요? 되돌릴 수 없습니다.")) return;
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => p.id !== projectId));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function renderProjectLink(project: Project) {
    const href = `/project/${project.id}`;
    const isActive = pathname === href;

    return (
      <div key={project.id} className="flex items-center gap-1">
        <Link
          href={href}
          className={`block flex-1 truncate rounded-lg px-3 py-2 text-sm shadow-sm transition ${
            isActive
              ? "bg-orange font-medium text-white"
              : "bg-orange-light text-ink/80 hover:bg-orange-light/70"
          }`}
        >
          {project.name}
        </Link>
        {project.role === "owner" && (
          <button
            type="button"
            onClick={() => handleDeleteProject(project.id)}
            aria-label="프로젝트 삭제"
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-ink/40 transition hover:bg-red-50 hover:text-red-600"
          >
            ×
          </button>
        )}
      </div>
    );
  }

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-shrink-0 flex-col border-r border-ink/10 bg-white p-4">
      <Link href="/" className="block text-sm font-semibold text-ink/70 hover:text-ink">
        {username || "내"} 프로젝트
      </Link>
      <div className="mb-6 mt-2 flex items-center gap-2 text-xs">
        {githubConnected ? (
          <>
            <span className="text-green-600">@{githubUsername}</span>
            <button
              type="button"
              onClick={() =>
                disconnectGithub()
                  .then(() => {
                    setGithubConnected(false);
                    setGithubUsername(null);
                  })
                  .catch((err) => setError((err as Error).message))
              }
              className="rounded border border-ink/15 px-2 py-0.5 text-ink/70 hover:bg-orange-light/40"
            >
              연결 해제
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => connectGithub().catch((err) => setError((err as Error).message))}
            className="rounded border border-ink/15 px-2 py-0.5 text-ink/70 hover:bg-orange-light/40"
          >
            GitHub 연동
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="mb-2 text-xs text-red-600">
          {error}
        </p>
      )}
      <nav className="flex-1 space-y-4 overflow-y-auto">
        {ownedProjects.length > 0 && (
          <div className="space-y-1">
            {ownedProjects.map(renderProjectLink)}
          </div>
        )}
        <div>
          <p className="mb-1 px-3 text-xs font-medium text-ink/40">
            참여하고 있는 프로젝트
          </p>
          {memberProjects.length > 0 ? (
            <div className="space-y-1">
              {memberProjects.map(renderProjectLink)}
            </div>
          ) : (
            <p className="px-3 text-sm text-ink/40">참여중인 프로젝트가 없습니다</p>
          )}
        </div>
      </nav>
    </aside>
  );
}
