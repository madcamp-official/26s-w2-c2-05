"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { onboardProject } from "@/lib/projects";

const PRINCIPLE_OPTIONS = [
  { id: "tdd", label: "TDD (테스트 주도 개발)" },
  { id: "conventional_commits", label: "Conventional Commits (커밋 메시지 규칙)" },
  { id: "code_review_required", label: "코드 리뷰 필수" },
  { id: "small_prs", label: "작은 단위로 PR 쪼개기" },
  { id: "trunk_based_development", label: "트렁크 기반 개발 (긴 브랜치 지양)" },
  { id: "documentation_required", label: "문서화 필수" },
];

export default function OnboardingPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();

  const [principles, setPrinciples] = useState<Set<string>>(new Set());
  const [techStack, setTechStack] = useState("");
  const [teamOrIndividual, setTeamOrIndividual] = useState<"team" | "individual">("team");
  const [indentStyle, setIndentStyle] = useState<"tabs" | "spaces">("spaces");
  const [customRequirements, setCustomRequirements] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function togglePrinciple(id: string) {
    setPrinciples((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSkip() {
    router.push(`/project/${projectId}`);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onboardProject(projectId, {
        principles: Array.from(principles),
        tech_stack: techStack,
        team_or_individual: teamOrIndividual,
        indent_style: indentStyle,
        custom_requirements: customRequirements,
      });
      router.push(`/project/${projectId}`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 py-12">
      <div className="text-center">
        <h1 className="text-xl font-semibold text-ink">프로젝트 온보딩</h1>
        <p className="mt-2 text-sm text-ink/60">
          간단히 답해주시면 첫 CLAUDE.md 초안을 만들어드려요. 건너뛰어도 괜찮아요.
        </p>
      </div>
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-lg flex-col gap-5 rounded-lg border border-ink/10 bg-white p-6 shadow-sm"
      >
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium text-ink">따르고 싶은 개발 원칙 (복수 선택 가능)</legend>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {PRINCIPLE_OPTIONS.map((opt) => (
              <label key={opt.id} className="flex items-center gap-2 text-sm text-ink/80">
                <input
                  type="checkbox"
                  checked={principles.has(opt.id)}
                  onChange={() => togglePrinciple(opt.id)}
                  className="h-4 w-4 rounded border-ink/30 text-orange focus:ring-orange/30"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="flex flex-col gap-1 text-sm text-ink/80">
          기술 스택 (선택)
          <input
            value={techStack}
            onChange={(e) => setTechStack(e.target.value)}
            placeholder="예: Python, FastAPI"
            className="rounded-md border border-ink/15 px-3 py-2 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
          />
        </label>

        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium text-ink">팀 / 개인</legend>
          <div className="flex gap-4 text-sm text-ink/80">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="team_or_individual"
                checked={teamOrIndividual === "team"}
                onChange={() => setTeamOrIndividual("team")}
                className="h-4 w-4 text-orange focus:ring-orange/30"
              />
              팀
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="team_or_individual"
                checked={teamOrIndividual === "individual"}
                onChange={() => setTeamOrIndividual("individual")}
                className="h-4 w-4 text-orange focus:ring-orange/30"
              />
              개인
            </label>
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium text-ink">들여쓰기 스타일</legend>
          <div className="flex gap-4 text-sm text-ink/80">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="indent_style"
                checked={indentStyle === "spaces"}
                onChange={() => setIndentStyle("spaces")}
                className="h-4 w-4 text-orange focus:ring-orange/30"
              />
              스페이스
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="indent_style"
                checked={indentStyle === "tabs"}
                onChange={() => setIndentStyle("tabs")}
                className="h-4 w-4 text-orange focus:ring-orange/30"
              />
              탭
            </label>
          </div>
        </fieldset>

        <label className="flex flex-col gap-1 text-sm text-ink/80">
          기타 요구사항 (선택)
          <textarea
            value={customRequirements}
            onChange={(e) => setCustomRequirements(e.target.value)}
            placeholder="자유롭게 적어주세요"
            rows={3}
            className="rounded-md border border-ink/15 px-3 py-2 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={submitting}
            className="flex-1 rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark disabled:opacity-60"
          >
            {submitting ? "만드는 중..." : "CLAUDE.md 만들기"}
          </button>
          <button
            type="button"
            onClick={handleSkip}
            disabled={submitting}
            className="rounded-md border border-ink/15 px-4 py-2 text-sm text-ink/70 transition hover:bg-ink/5 disabled:opacity-60"
          >
            건너뛰기
          </button>
        </div>
      </form>
    </div>
  );
}
