"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createProject } from "@/lib/projects";

export default function Home() {
  const [name, setName] = useState("");
  const router = useRouter();

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const project = createProject(trimmed);
    router.push(`/project/${project.id}`);
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <div>
        <h1 className="text-xl font-semibold text-ink">
          프로젝트를 선택하거나 새로 만들어보세요
        </h1>
        <p className="mt-2 text-sm text-ink/60">
          왼쪽에서 기존 프로젝트를 클릭하거나, 아래에서 새 프로젝트를 만들 수 있어요.
        </p>
      </div>
      <form onSubmit={handleCreate} className="flex w-full max-w-sm flex-col gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="새 프로젝트 이름"
          className="rounded-md border border-ink/15 px-3 py-2 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
        />
        <button
          type="submit"
          className="rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark"
        >
          프로젝트 만들기
        </button>
      </form>
    </div>
  );
}
