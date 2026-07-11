"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { listProjects, type Project } from "@/lib/projects";

export default function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([]);
  const pathname = usePathname();

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]));
  }, [pathname]);

  if (pathname === "/login") return null;

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-shrink-0 flex-col border-r border-ink/10 bg-white p-4">
      <h2 className="mb-6 text-sm font-semibold text-ink/70">내 프로젝트</h2>
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
