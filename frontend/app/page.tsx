"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createProject } from "@/lib/projects";
import { logout, connectGithub, disconnectGithub, getGithubStatus } from "@/lib/auth";

export default function Home() {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [githubConnected, setGithubConnected] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const githubStatus = searchParams.get("github");

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.push("/login");
    } else {
      setAuthorized(true);
    }
  }, [router]);

  useEffect(() => {
    if (!authorized) return;
    getGithubStatus()
      .then((s) => setGithubConnected(s.connected))
      .catch(() => setGithubConnected(false));
  }, [authorized, githubStatus]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    setError(null);
    try {
      const project = await createProject(trimmed);
      router.push(`/project/${project.id}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function handleLogout() {
    logout();
    router.push("/login");
  }

  if (!authorized) return null;

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <button
        type="button"
        onClick={handleLogout}
        className="absolute right-6 top-6 rounded-md border border-ink/15 px-3 py-1.5 text-sm text-ink/70 transition hover:bg-ink/5"
      >
        로그아웃
      </button>
      {githubStatus === "connected" && (
        <p className="text-sm text-green-600">GitHub 계정이 연결됐어요.</p>
      )}
      {githubStatus === "error" && (
        <p role="alert" className="text-sm text-red-600">GitHub 연결에 실패했어요.</p>
      )}
      <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-sm font-medium text-ink/70">GitHub 연동</h2>
        {githubConnected ? (
          <div className="flex items-center gap-3">
            <p className="text-sm text-green-600">GitHub 계정이 연결되어 있어요.</p>
            <button
              type="button"
              onClick={() =>
                disconnectGithub()
                  .then(() => setGithubConnected(false))
                  .catch((err) => setError((err as Error).message))
              }
              className="rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
            >
              연결 해제
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => connectGithub().catch((err) => setError((err as Error).message))}
            className="rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
          >
            GitHub 계정 연결
          </button>
        )}
      </div>
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
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
