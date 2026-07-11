"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { getProject, saveProjectContent, type Project } from "@/lib/projects";

type Recommendation = {
  id: string;
  reason: string;
  suggestedText: string;
};

const SAMPLE_RECOMMENDATIONS: Recommendation[] = [
  {
    id: "r1",
    reason: "탭 대신 스페이스로 들여쓰기를 여러 번 요청하셨어요.",
    suggestedText: "- 들여쓰기는 탭이 아닌 스페이스 2칸을 사용한다.",
  },
  {
    id: "r2",
    reason: "커밋 전에 항상 npm test를 직접 실행하셨어요.",
    suggestedText: "- 커밋하기 전에 반드시 `npm test`를 실행해서 통과를 확인한다.",
  },
];

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | undefined>();
  const [content, setContent] = useState("");
  const [applied, setApplied] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSavedContent = useRef<string | null>(null);

  useEffect(() => {
    lastSavedContent.current = null;
    getProject(projectId)
      .then((p) => {
        setProject(p);
        setContent(p.content);
        setApplied(new Set());
        lastSavedContent.current = p.content;
      })
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  useEffect(() => {
    if (lastSavedContent.current === null || content === lastSavedContent.current) return;
    const timeout = setTimeout(() => {
      saveProjectContent(projectId, content)
        .then(() => {
          lastSavedContent.current = content;
        })
        .catch((err) => setError((err as Error).message));
    }, 500);
    return () => clearTimeout(timeout);
  }, [projectId, content]);

  function applyRecommendation(rec: Recommendation) {
    setContent((prev) => `${prev.trimEnd()}\n${rec.suggestedText}\n`);
    setApplied((prev) => new Set(prev).add(rec.id));
  }

  function handleDownload() {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "CLAUDE.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-ink">
          {project?.name ?? "프로젝트"} · CLAUDE.md 편집기
        </h1>
        <p className="mt-1 text-sm text-ink/60">
          세션에서 발견된 패턴을 참고해서 이 프로젝트의 CLAUDE.md를 다듬어보세요.
        </p>
      </header>

      {error && (
        <p role="alert" className="mb-4 text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <section>
          <label className="mb-2 block text-sm font-medium text-ink/70">
            CLAUDE.md 내용
          </label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            spellCheck={false}
            className="h-[420px] w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={handleDownload}
              className="rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark"
            >
              다운로드
            </button>
            <button
              onClick={handleCopy}
              className="rounded-md border border-ink/15 bg-white px-4 py-2 text-sm font-medium text-ink transition hover:bg-orange-light/40"
            >
              {copied ? "복사됨" : "복사하기"}
            </button>
          </div>
        </section>

        <aside>
          <h2 className="mb-2 text-sm font-medium text-ink/70">추천 (예시)</h2>
          <div className="flex flex-col gap-3">
            {SAMPLE_RECOMMENDATIONS.map((rec) => {
              const isApplied = applied.has(rec.id);
              return (
                <div
                  key={rec.id}
                  className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm"
                >
                  <p className="text-sm text-ink/80">{rec.reason}</p>
                  <code className="mt-2 block rounded bg-orange-light/40 px-2 py-1 text-xs text-ink/70">
                    {rec.suggestedText}
                  </code>
                  <button
                    onClick={() => applyRecommendation(rec)}
                    disabled={isApplied}
                    className="mt-3 w-full rounded-md bg-orange px-3 py-1.5 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:bg-ink/20"
                  >
                    {isApplied ? "반영됨" : "적용하기"}
                  </button>
                </div>
              );
            })}
          </div>
        </aside>
      </div>
    </main>
  );
}
