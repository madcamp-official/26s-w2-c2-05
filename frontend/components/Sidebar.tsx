"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { listProjects, type Project } from "@/lib/projects";
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

  if (pathname === "/login" || pathname === "/signup") return null;

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-shrink-0 flex-col border-r border-ink/10 bg-white p-4">
      <Link href="/" className="block text-sm font-semibold text-ink/70 hover:text-ink">
        {username || "내"} 프로젝트
      </Link>
      <div className="mb-6 mt-2 flex items-center gap-2 text-xs">
        {githubConnected ? (
          <>
            <span className="text-green-600">GitHub: @{githubUsername}</span>
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
      <nav className="flex-1 space-y-1 overflow-y-auto">
        {projects.length === 0 && (
          <p className="text-sm text-ink/40">아직 프로젝트가 없어요.</p>
        )}
        {projects.map((project) => {
          const href = `/project/${project.id}`;
          const isActive = pathname === href;
          return (
            <Link
              key={project.id}
              href={href}
              className={`block truncate rounded-lg px-3 py-2 text-sm shadow-sm transition ${
                isActive
                  ? "bg-orange font-medium text-white"
                  : "bg-orange-light text-ink/80 hover:bg-orange-light/70"
              }`}
            >
              {project.name}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
