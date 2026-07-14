"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  getProject,
  saveProjectContent,
  saveProjectHooks,
  setGithubRepo,
  pushToGithub,
  inviteMember,
  listRevisions,
  getRevision,
  renameProject,
  uploadSession,
  getMyRecommendations,
  getTeamRecommendations,
  applyRecommendationGroup,
  applyPersonalRecommendationApi,
  listSkills,
  saveSkill,
  deleteSkill,
  SaveConflictError,
  type Project,
  type Revision,
  type RevisionDetail,
  type PersonalRecommendation,
  type TeamRecommendation,
  type HookPayload,
  type ClaudeMdPayload,
  type Skill,
  type SkillPayload,
} from "@/lib/projects";
import { getGithubStatus } from "@/lib/auth";

type OnlineUser = {
  user_id: number;
  username: string;
};

const REPO_URL_RE = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?(\.git)?$/;
const REPO_SHORT_RE = /^[\w.-]+\/[\w.-]+$/;

function isValidRepoInput(value: string): boolean {
  return REPO_URL_RE.test(value) || REPO_SHORT_RE.test(value);
}

type HookEntry = { matcher: string; hooks: { type: string; command: string }[] };

function mergeHookIntoJson(
  hooksJson: string,
  event: string,
  matcher: string,
  command: string
): string {
  const parsed = JSON.parse(hooksJson);
  if (typeof parsed.hooks !== "object" || parsed.hooks === null) {
    parsed.hooks = {};
  }
  const entries: HookEntry[] = parsed.hooks[event] ?? [];
  const matcherEntry = entries.find((e) => e.matcher === matcher);
  if (matcherEntry) {
    if (!matcherEntry.hooks.some((h) => h.command === command)) {
      matcherEntry.hooks.push({ type: "command", command });
    }
  } else {
    entries.push({ matcher, hooks: [{ type: "command", command }] });
  }
  parsed.hooks[event] = entries;
  return JSON.stringify(parsed, null, 2);
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | undefined>();
  const [content, setContent] = useState("");
  const [hooksContent, setHooksContent] = useState("");
  const [editorTab, setEditorTab] = useState<"content" | "hooks" | "skill">("content");
  const [error, setError] = useState<string | null>(null);
  const [repoInput, setRepoInput] = useState("");
  const [pushing, setPushing] = useState(false);
  const [pushed, setPushed] = useState(false);
  const [githubConnected, setGithubConnected] = useState(true);
  const [inviteUsername, setInviteUsername] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState<string | null>(null);
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [editingRepo, setEditingRepo] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [previewRevision, setPreviewRevision] = useState<RevisionDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [personalRecs, setPersonalRecs] = useState<PersonalRecommendation[]>([]);
  const [teamRecs, setTeamRecs] = useState<TeamRecommendation[]>([]);
  const [pendingAppliedPersonalIds, setPendingAppliedPersonalIds] = useState<Set<string>>(new Set());
  const [pendingAppliedGroupIds, setPendingAppliedGroupIds] = useState<Set<string>>(new Set());
  const [recTab, setRecTab] = useState<"my" | "team">("my");
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [skillNameInput, setSkillNameInput] = useState("");
  const [skillDescriptionInput, setSkillDescriptionInput] = useState("");
  const [skillStepsInput, setSkillStepsInput] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [handTypedConflict, setHandTypedConflict] = useState<
    { target: "content" | "hooks"; latestContent: string } | null
  >(null);
  const [showLatestPreview, setShowLatestPreview] = useState(false);
  const sessionFileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const activeRecType =
    editorTab === "content" ? "claude_md" : editorTab === "hooks" ? "hook" : "skill";
  const visiblePersonalRecs = personalRecs.filter((rec) => rec.type === activeRecType);
  const visibleTeamRecs = teamRecs.filter((rec) => rec.type === activeRecType);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId}?token=${token}`);
    wsRef.current = ws;

    return () => {
      ws.close();
      wsRef.current = null;
      setOnlineUsers([]);
    };
  }, [projectId]);

  useEffect(() => {
    const ws = wsRef.current;
    if (!ws) return;
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.online_users) {
        setOnlineUsers(data.online_users);
        return;
      }
      if (data.type === "content_updated") {
        reconcileWithServer(
          data.target,
          `${data.updated_by ?? "팀원"}님이 방금 저장한 내용이 반영되었어요`
        );
      }
    };
  }, [
    pendingAppliedPersonalIds,
    pendingAppliedGroupIds,
    personalRecs,
    teamRecs,
    project,
    content,
    hooksContent,
  ]);

  useEffect(() => {
    getGithubStatus()
      .then((s) => setGithubConnected(s.connected))
      .catch(() => setGithubConnected(true));
  }, []);

  useEffect(() => {
    getProject(projectId)
      .then((p) => {
        setProject(p);
        setContent(p.content);
        setHooksContent(p.hooks_content);
        setRepoInput(p.github_repo ?? "");
      })
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  useEffect(() => {
    listRevisions(projectId)
      .then(setRevisions)
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  useEffect(() => {
    getMyRecommendations(projectId)
      .then(setPersonalRecs)
      .catch((err) => setError((err as Error).message));
    getTeamRecommendations(projectId)
      .then(setTeamRecs)
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  useEffect(() => {
    listSkills(projectId)
      .then(setSkills)
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  async function handleUploadSession(file: File) {
    setError(null);
    setUploadMessage(null);
    setUploading(true);
    try {
      const result = await uploadSession(projectId, file);
      setUploadMessage(
        result.status === "no_patterns"
          ? "반복되는 패턴을 찾지 못했어요"
          : "업로드 완료! 추천을 확인해보세요"
      );
      const [myRecs, latestTeamRecs] = await Promise.all([
        getMyRecommendations(projectId),
        getTeamRecommendations(projectId),
      ]);
      setPersonalRecs(myRecs);
      setTeamRecs(latestTeamRecs);
      setPendingAppliedPersonalIds(new Set());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function selectSkill(skill: Skill) {
    setSelectedSkillId(skill.id);
    setSkillNameInput(skill.name);
    setSkillDescriptionInput(skill.description);
    setSkillStepsInput(skill.steps_content);
  }

  async function handleDeleteSkill() {
    if (!selectedSkillId) return;
    setError(null);
    try {
      await deleteSkill(projectId, selectedSkillId);
      setSkills((prev) => prev.filter((s) => s.id !== selectedSkillId));
      setSelectedSkillId(null);
      setSkillNameInput("");
      setSkillDescriptionInput("");
      setSkillStepsInput("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleApplySkillPersonal(rec: PersonalRecommendation) {
    setError(null);
    try {
      await applyPersonalRecommendationApi(projectId, rec.id);
      const [updatedSkills, updatedPersonalRecs] = await Promise.all([
        listSkills(projectId),
        getMyRecommendations(projectId),
      ]);
      setSkills(updatedSkills);
      setPersonalRecs(updatedPersonalRecs);
      const payload = rec.payload as SkillPayload;
      const created = updatedSkills.find((s) => s.name === payload.skill_name);
      setEditorTab("skill");
      if (created) selectSkill(created);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleApplySkillTeam(rec: TeamRecommendation) {
    setError(null);
    try {
      await applyRecommendationGroup(projectId, rec.id);
      const [updatedSkills, updatedTeamRecs] = await Promise.all([
        listSkills(projectId),
        getTeamRecommendations(projectId),
      ]);
      setSkills(updatedSkills);
      setTeamRecs(updatedTeamRecs);
      const created = updatedSkills.find((s) => s.description === rec.representative_text);
      setEditorTab("skill");
      if (created) selectSkill(created);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function formatClaudeMdCandidate(payload: ClaudeMdPayload): string {
    return `- ${payload.suggested_text}`;
  }

  function applyPersonalRecommendation(rec: PersonalRecommendation) {
    if (rec.type === "hook") {
      const hook = rec.payload as HookPayload;
      try {
        setHooksContent(mergeHookIntoJson(hooksContent, hook.event, hook.matcher, hook.command));
      } catch {
        setError("Hooks 탭의 JSON이 올바르지 않아 추천을 적용할 수 없어요. 먼저 JSON을 고쳐주세요.");
        return;
      }
    } else {
      setContent(
        (prev) => `${prev.trimEnd()}\n${formatClaudeMdCandidate(rec.payload as ClaudeMdPayload)}\n`
      );
    }
    setPendingAppliedPersonalIds((prev) => new Set(prev).add(rec.id));
  }

  function applyTeamRecommendation(rec: TeamRecommendation) {
    if (rec.type === "hook") {
      if (!rec.event || !rec.matcher) {
        setError("이 팀 추천은 event/matcher 정보가 없어 적용할 수 없어요.");
        return;
      }
      try {
        setHooksContent(
          mergeHookIntoJson(hooksContent, rec.event, rec.matcher, rec.representative_text)
        );
      } catch {
        setError("Hooks 탭의 JSON이 올바르지 않아 추천을 적용할 수 없어요. 먼저 JSON을 고쳐주세요.");
        return;
      }
    } else {
      setContent((prev) => `${prev.trimEnd()}\n- ${rec.representative_text}\n`);
    }
    setPendingAppliedGroupIds((prev) => new Set(prev).add(rec.id));
  }

  function buildMergedContent(base: string): string {
    let merged = base;
    for (const id of pendingAppliedPersonalIds) {
      const rec = personalRecs.find((r) => r.id === id && r.type === "claude_md");
      if (rec) {
        merged = `${merged.trimEnd()}\n${formatClaudeMdCandidate(rec.payload as ClaudeMdPayload)}\n`;
      }
    }
    for (const id of pendingAppliedGroupIds) {
      const rec = teamRecs.find((r) => r.id === id && r.type === "claude_md");
      if (rec) {
        merged = `${merged.trimEnd()}\n- ${rec.representative_text}\n`;
      }
    }
    return merged;
  }

  function buildMergedHooks(base: string): string {
    let merged = base;
    for (const id of pendingAppliedPersonalIds) {
      const rec = personalRecs.find((r) => r.id === id && r.type === "hook");
      if (rec) {
        const hook = rec.payload as HookPayload;
        try {
          merged = mergeHookIntoJson(merged, hook.event, hook.matcher, hook.command);
        } catch {
          // base가 유효하지 않은 JSON이면 그대로 두고, 저장 시 기존 JSON 검증 에러로 안내됨
        }
      }
    }
    for (const id of pendingAppliedGroupIds) {
      const rec = teamRecs.find((r) => r.id === id && r.type === "hook");
      if (rec && rec.event && rec.matcher) {
        try {
          merged = mergeHookIntoJson(merged, rec.event, rec.matcher, rec.representative_text);
        } catch {
          // 위와 동일
        }
      }
    }
    return merged;
  }

  async function reconcileWithServer(target: "content" | "hooks", message: string) {
    let latest: Project;
    try {
      latest = await getProject(projectId);
    } catch {
      setError("최신 내용을 불러오지 못했어요. 잠시 후 다시 시도해주세요.");
      return;
    }
    listRevisions(projectId).then(setRevisions).catch(() => {});

    if (target === "content") {
      const expectedFromRecsOnly = buildMergedContent(project?.content ?? "");
      if (content === expectedFromRecsOnly) {
        setContent(buildMergedContent(latest.content));
        setProject(latest);
        setNotice(message);
      } else {
        setHandTypedConflict({ target: "content", latestContent: latest.content });
      }
    } else {
      const expectedFromRecsOnly = buildMergedHooks(project?.hooks_content ?? "");
      if (hooksContent === expectedFromRecsOnly) {
        setHooksContent(buildMergedHooks(latest.hooks_content));
        setProject(latest);
        setNotice(message);
      } else {
        setHandTypedConflict({ target: "hooks", latestContent: latest.hooks_content });
      }
    }
  }

  async function handleSave() {
    setError(null);
    setNotice(null);
    setSaving(true);
    try {
      if (editorTab === "skill") {
        if (!selectedSkillId) return;
        const updated = await saveSkill(projectId, selectedSkillId, {
          name: skillNameInput,
          description: skillDescriptionInput,
          steps_content: skillStepsInput,
        });
        setSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
        const latest = await listRevisions(projectId);
        setRevisions(latest);
        return;
      }

      if (editorTab === "hooks") {
        let updated: Project;
        try {
          updated = await saveProjectHooks(projectId, hooksContent, project?.updated_at);
        } catch (err) {
          if (err instanceof SaveConflictError) {
            await reconcileWithServer(
              "hooks",
              "다른 팀원이 먼저 저장했어요. 최신 내용에 회원님의 변경사항을 다시 합쳤어요. 저장을 다시 눌러주세요."
            );
          } else {
            setError((err as Error).message);
          }
          return;
        }
        setProject(updated);
        const latest = await listRevisions(projectId);
        setRevisions(latest);

        const hookGroupIds = Array.from(pendingAppliedGroupIds).filter(
          (id) => teamRecs.find((r) => r.id === id)?.type === "hook"
        );
        if (hookGroupIds.length > 0) {
          await Promise.all(
            hookGroupIds.map((groupId) => applyRecommendationGroup(projectId, groupId))
          );
          setPendingAppliedGroupIds((prev) => {
            const next = new Set(prev);
            hookGroupIds.forEach((id) => next.delete(id));
            return next;
          });
          setTeamRecs(await getTeamRecommendations(projectId));
        }

        const hookPersonalIds = Array.from(pendingAppliedPersonalIds).filter(
          (id) => personalRecs.find((r) => r.id === id)?.type === "hook"
        );
        if (hookPersonalIds.length > 0) {
          await Promise.all(
            hookPersonalIds.map((recId) => applyPersonalRecommendationApi(projectId, recId))
          );
          setPendingAppliedPersonalIds((prev) => {
            const next = new Set(prev);
            hookPersonalIds.forEach((id) => next.delete(id));
            return next;
          });
          setPersonalRecs(await getMyRecommendations(projectId));
        }
        return;
      }

      let updated: Project;
      try {
        updated = await saveProjectContent(projectId, content, project?.updated_at);
      } catch (err) {
        if (err instanceof SaveConflictError) {
          await reconcileWithServer(
            "content",
            "다른 팀원이 먼저 저장했어요. 최신 내용에 회원님의 변경사항을 다시 합쳤어요. 저장을 다시 눌러주세요."
          );
        } else {
          setError((err as Error).message);
        }
        return;
      }
      setProject(updated);
      const latest = await listRevisions(projectId);
      setRevisions(latest);

      const claudeMdGroupIds = Array.from(pendingAppliedGroupIds).filter(
        (id) => teamRecs.find((r) => r.id === id)?.type === "claude_md"
      );
      if (claudeMdGroupIds.length > 0) {
        await Promise.all(
          claudeMdGroupIds.map((groupId) => applyRecommendationGroup(projectId, groupId))
        );
        setPendingAppliedGroupIds((prev) => {
          const next = new Set(prev);
          claudeMdGroupIds.forEach((id) => next.delete(id));
          return next;
        });
      }

      const claudeMdPersonalIds = Array.from(pendingAppliedPersonalIds).filter(
        (id) => personalRecs.find((r) => r.id === id)?.type === "claude_md"
      );
      if (claudeMdPersonalIds.length > 0) {
        await Promise.all(
          claudeMdPersonalIds.map((recId) => applyPersonalRecommendationApi(projectId, recId))
        );
        setPendingAppliedPersonalIds((prev) => {
          const next = new Set(prev);
          claudeMdPersonalIds.forEach((id) => next.delete(id));
          return next;
        });
      }

      window.location.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleOpenRevision(revisionId: string) {
    setError(null);
    try {
      const revision = await getRevision(projectId, revisionId);
      setPreviewRevision(revision);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function startEditingName() {
    setNameInput(project?.name ?? "");
    setEditingName(true);
  }

  async function submitEditingName() {
    const name = nameInput.trim();
    if (!name || name === project?.name) {
      setEditingName(false);
      return;
    }
    try {
      await renameProject(projectId, name);
      window.location.reload();
    } catch (err) {
      setError((err as Error).message);
      setEditingName(false);
    }
  }

  async function handleSaveRepo(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = repoInput.trim();
    if (!isValidRepoInput(trimmed)) {
      setError("올바른 GitHub repo 형식이 아니에요 (예: owner/repo 또는 https://github.com/owner/repo)");
      return;
    }
    try {
      const updated = await setGithubRepo(projectId, trimmed);
      setProject(updated);
      setEditingRepo(false);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteMessage(null);
    const username = inviteUsername.trim();
    if (!username) {
      setInviteMessage("username을 입력해주세요");
      return;
    }
    setInviting(true);
    try {
      await inviteMember(projectId, username);
      setInviteMessage("초대했습니다");
      setInviteUsername("");
    } catch (err) {
      setInviteMessage((err as Error).message);
    } finally {
      setInviting(false);
    }
  }

  async function handlePush() {
    setError(null);
    setPushed(false);
    setPushing(true);
    try {
      await pushToGithub(projectId);
      setPushed(true);
      setTimeout(() => setPushed(false), 2000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPushing(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          {editingName ? (
            <input
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitEditingName();
                if (e.key === "Escape") setEditingName(false);
              }}
              onBlur={submitEditingName}
              autoFocus
              className="rounded-md border border-orange px-2 py-1 text-2xl font-semibold text-ink focus:outline-none focus:ring-2 focus:ring-orange/30"
            />
          ) : (
            <h1
              onClick={() => project?.role === "owner" && startEditingName()}
              className={`text-2xl font-semibold text-ink ${
                project?.role === "owner" ? "cursor-pointer hover:underline" : ""
              }`}
            >
              {project?.name ?? "프로젝트"}
            </h1>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          {onlineUsers.map((u) => (
            <span
              key={u.user_id}
              className="rounded-full bg-orange-light px-2.5 py-1 text-xs font-medium text-ink/70"
            >
              {u.username}
            </span>
          ))}
          {project?.role === "owner" && (
            <button
              type="button"
              onClick={() => {
                setInviteMessage(null);
                setInviteModalOpen(true);
              }}
              aria-label="프로젝트에 초대"
              className="flex h-6 w-6 items-center justify-center rounded-full border border-ink/15 bg-white text-sm text-ink/70 transition hover:bg-orange-light/40"
            >
              +
            </button>
          )}
        </div>
      </header>

      {inviteModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setInviteModalOpen(false)}
        >
          <div
            className="w-80 rounded-lg bg-white p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-3 text-sm font-medium text-ink/80">프로젝트에 초대</h3>
            <form onSubmit={handleInvite} className="flex flex-col gap-2">
              <input
                value={inviteUsername}
                onChange={(e) => setInviteUsername(e.target.value)}
                placeholder="초대할 username"
                autoFocus
                className="w-full rounded-md border border-ink/15 px-3 py-1.5 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
              />
              {inviteMessage && <p className="text-sm text-ink/70">{inviteMessage}</p>}
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setInviteModalOpen(false)}
                  className="rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={inviting}
                  className="rounded-md bg-orange px-3 py-1.5 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {inviting ? "초대 중..." : "초대하기"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="mb-4 text-sm text-red-600">
          {error}
        </p>
      )}
      {notice && (
        <p className="mb-4 text-sm text-orange-dark">
          {notice}
        </p>
      )}
      {handTypedConflict && (
        <div className="mb-4 flex items-center justify-between gap-3 rounded-md border border-orange/30 bg-orange-light/40 px-3 py-2 text-sm text-ink/80">
          <span>
            팀원이 방금 {handTypedConflict.target === "content" ? "CLAUDE.md" : "Hooks"}를
            저장했지만, 직접 수정한 내용이 있어 자동으로 합치지 못했어요.
          </span>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => setShowLatestPreview(true)}
              className="whitespace-nowrap rounded-md border border-ink/15 bg-white px-2.5 py-1 text-xs text-ink transition hover:bg-orange-light/40"
            >
              최신 내용 보기
            </button>
            <button
              type="button"
              onClick={() => setHandTypedConflict(null)}
              className="whitespace-nowrap rounded-md border border-ink/15 bg-white px-2.5 py-1 text-xs text-ink transition hover:bg-orange-light/40"
            >
              닫기
            </button>
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[4fr_4fr_2fr]">
        <section>
          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
            {project?.role === "owner" && !githubConnected && (
              <p className="mb-3 text-sm text-red-600">
                GitHub 계정을 연동해주세요
              </p>
            )}
            {project?.role === "owner" && editingRepo ? (
              <form onSubmit={handleSaveRepo} className="flex gap-2">
                <input
                  value={repoInput}
                  onChange={(e) => setRepoInput(e.target.value)}
                  placeholder="owner/repo"
                  autoFocus
                  className="flex-1 rounded-md border border-ink/15 px-3 py-2 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                />
                <button
                  type="submit"
                  className="rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
                >
                  저장
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRepoInput(project?.github_repo ?? "");
                    setEditingRepo(false);
                  }}
                  className="rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
                >
                  취소
                </button>
              </form>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <span className="text-base font-semibold text-ink/80">
                  {project?.github_repo ?? "설정된 repo가 없습니다"}
                </span>
                {project?.role === "owner" && (
                  <button
                    type="button"
                    onClick={() => setEditingRepo(true)}
                    className="rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
                  >
                    repo 수정
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="mb-2 mt-10 flex gap-1">
            <button
              type="button"
              onClick={() => setEditorTab("content")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                editorTab === "content"
                  ? "bg-orange text-white"
                  : "text-ink/60 hover:bg-orange-light/40"
              }`}
            >
              CLAUDE.md
            </button>
            <button
              type="button"
              onClick={() => setEditorTab("hooks")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                editorTab === "hooks"
                  ? "bg-orange text-white"
                  : "text-ink/60 hover:bg-orange-light/40"
              }`}
            >
              Hooks
            </button>
            <button
              type="button"
              onClick={() => setEditorTab("skill")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                editorTab === "skill"
                  ? "bg-orange text-white"
                  : "text-ink/60 hover:bg-orange-light/40"
              }`}
            >
              Skill
            </button>
          </div>
          <label className="mb-2 block text-sm font-medium text-ink/70">
            {editorTab === "content"
              ? "CLAUDE.md 내용을 수정 후 저장을 눌러주세요"
              : editorTab === "hooks"
              ? ".claude/settings.json 내용을 수정 후 저장을 눌러주세요 (JSON 형식)"
              : "왼쪽에서 스킬을 선택해 수정 후 저장을 눌러주세요"}
          </label>
          {editorTab === "skill" ? (
            <div className="flex h-[420px] gap-4">
              <ul className="w-40 flex-shrink-0 overflow-y-auto flex flex-col gap-1">
                {skills.length === 0 && (
                  <p className="text-xs text-ink/40">아직 스킬이 없습니다</p>
                )}
                {skills.map((skill) => (
                  <li key={skill.id}>
                    <button
                      type="button"
                      onClick={() => selectSkill(skill)}
                      className={`w-full rounded-md px-2 py-1.5 text-left text-sm transition ${
                        selectedSkillId === skill.id
                          ? "bg-orange text-white"
                          : "text-ink/70 hover:bg-orange-light/40"
                      }`}
                    >
                      {skill.name}
                    </button>
                  </li>
                ))}
              </ul>
              {selectedSkillId ? (
                <div className="flex flex-1 flex-col gap-2">
                  <input
                    value={skillNameInput}
                    onChange={(e) => setSkillNameInput(e.target.value)}
                    placeholder="스킬 이름 (kebab-case)"
                    className="rounded-md border border-ink/15 px-3 py-2 text-sm font-mono focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                  />
                  <input
                    value={skillDescriptionInput}
                    onChange={(e) => setSkillDescriptionInput(e.target.value)}
                    placeholder="한 줄 설명"
                    className="rounded-md border border-ink/15 px-3 py-2 text-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                  />
                  <textarea
                    value={skillStepsInput}
                    onChange={(e) => setSkillStepsInput(e.target.value)}
                    spellCheck={false}
                    className="flex-1 w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
                  />
                  <button
                    type="button"
                    onClick={handleDeleteSkill}
                    className="self-start rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-600 transition hover:bg-red-50"
                  >
                    이 스킬 삭제
                  </button>
                </div>
              ) : (
                <p className="flex-1 text-sm text-ink/40">
                  왼쪽에서 스킬을 선택하거나, 오른쪽 추천 카드에서 스킬을 적용해보세요.
                </p>
              )}
            </div>
          ) : editorTab === "content" ? (
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              spellCheck={false}
              className="h-[420px] w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
            />
          ) : (
            <textarea
              value={hooksContent}
              onChange={(e) => setHooksContent(e.target.value)}
              spellCheck={false}
              className="h-[420px] w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
            />
          )}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="shrink-0 whitespace-nowrap rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "저장 중..." : "저장"}
            </button>
            <div className="ml-auto flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={handlePush}
                disabled={pushing}
                className="shrink-0 whitespace-nowrap rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
              >
                {pushing ? "PUSH 중..." : pushed ? "PUSH 완료" : "PUSH"}
              </button>
            </div>
          </div>
        </section>

        <aside className="min-w-0">
          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-medium text-ink/70">세션 업로드</h2>
            <input
              ref={sessionFileInputRef}
              type="file"
              accept=".jsonl"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUploadSession(f);
                e.target.value = "";
              }}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => sessionFileInputRef.current?.click()}
              disabled={uploading}
              className="w-full rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading ? "업로드 중..." : "업로드"}
            </button>
            {uploadMessage && (
              <p className="mt-2 text-sm text-ink/70">{uploadMessage}</p>
            )}
            <p className="mt-3 text-xs leading-relaxed text-ink/50">
               <code className="rounded bg-orange-light/40 px-1">C:\Users\(username)\.claude\projects\
              </code>
              <br />
              세션 JSONL 파일은 위 링크 폴더안, 이 프로젝트 경로에 해당하는 하위 폴더에 있어요. 그중 가장 최근에 수정된 파일을 선택해주세요.
              <br />
              MAC의 경우 [command+shift+.]을 해야 숨김파일이 보입니다.
            </p>
          </div>

          <div className="mt-6 rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
            <div className="mb-2 flex gap-1">
              <button
                type="button"
                onClick={() => setRecTab("my")}
                className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                  recTab === "my"
                    ? "bg-orange text-white"
                    : "text-ink/60 hover:bg-orange-light/40"
                }`}
              >
                My
              </button>
              <button
                type="button"
                onClick={() => setRecTab("team")}
                className={`rounded-md px-3 py-1 text-sm font-medium transition ${
                  recTab === "team"
                    ? "bg-orange text-white"
                    : "text-ink/60 hover:bg-orange-light/40"
                }`}
              >
                Team
              </button>
            </div>

            {recTab === "my" ? (
              visiblePersonalRecs.length === 0 ? (
                <p className="text-sm text-ink/40">아직 추천이 없습니다</p>
              ) : (
                <div className="flex gap-3 overflow-x-auto pb-2">
                  {visiblePersonalRecs.map((rec) => {
                    const isApplied = rec.applied || pendingAppliedPersonalIds.has(rec.id);
                    return (
                      <div
                        key={rec.id}
                        className="w-64 flex-shrink-0 rounded-lg border border-ink/10 bg-white p-3 shadow-sm"
                      >
                        <p className="text-sm text-ink/80">{rec.payload.reason}</p>
                        <code className="mt-2 block rounded bg-orange-light/40 px-2 py-1 text-xs text-ink/70">
                          {rec.type === "claude_md"
                            ? (rec.payload as ClaudeMdPayload).suggested_text
                            : rec.type === "hook"
                            ? `${(rec.payload as HookPayload).event} → ${(rec.payload as HookPayload).command}`
                            : `${(rec.payload as SkillPayload).skill_name}: ${(rec.payload as SkillPayload).suggested_steps}`}
                        </code>
                        <button
                          type="button"
                          onClick={() =>
                            rec.type === "skill"
                              ? handleApplySkillPersonal(rec)
                              : applyPersonalRecommendation(rec)
                          }
                          disabled={isApplied}
                          className="mt-3 w-full rounded-md bg-orange px-3 py-1.5 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:bg-ink/20"
                        >
                          {isApplied ? "반영됨" : "적용하기"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )
            ) : visibleTeamRecs.length === 0 ? (
              <p className="text-sm text-ink/40">아직 팀 추천이 없습니다</p>
            ) : (
              <div className="flex gap-3 overflow-x-auto pb-2">
                {visibleTeamRecs.map((rec) => {
                  const isApplied = rec.applied || pendingAppliedGroupIds.has(rec.id);
                  return (
                    <div
                      key={rec.id}
                      className="w-64 flex-shrink-0 rounded-lg border border-ink/10 bg-white p-3 shadow-sm"
                    >
                      <p className="text-xs text-ink/50">
                        {rec.affected_members}명에게서 나온 규칙
                      </p>
                      <code className="mt-1 block rounded bg-orange-light/40 px-2 py-1 text-xs text-ink/70">
                        {rec.representative_text}
                      </code>
                      <button
                        type="button"
                        onClick={() =>
                          rec.type === "skill"
                            ? handleApplySkillTeam(rec)
                            : applyTeamRecommendation(rec)
                        }
                        disabled={isApplied}
                        className="mt-3 w-full rounded-md bg-orange px-3 py-1.5 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:bg-ink/20"
                      >
                        {isApplied ? "반영됨" : "적용하기"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </aside>

        <aside className="min-w-0">
          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-medium text-ink/70">변경 이력</h2>
            {revisions.length === 0 ? (
              <p className="text-sm text-ink/40">저장 기록이 없습니다</p>
            ) : (
              <ul className="flex flex-col gap-1.5">
                {revisions.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => handleOpenRevision(r.id)}
                      className="flex w-full flex-col items-start gap-1 rounded-md px-2 py-1.5 text-left text-sm text-ink/70 transition hover:bg-orange-light/40"
                    >
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                          r.target === "hooks"
                            ? "bg-orange-light/60 text-orange-dark"
                            : r.target === "skill"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-ink/10 text-ink/60"
                        }`}
                      >
                        {r.target === "hooks" ? "Hooks" : r.target === "skill" ? "Skill" : "CLAUDE.md"}
                      </span>
                      <span>
                        {new Date(r.created_at).toLocaleString()} · {r.username}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>

      {previewRevision && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setPreviewRevision(null)}
        >
          <div
            className="max-h-[80vh] w-[32rem] overflow-y-auto rounded-lg bg-white p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-sm font-medium text-ink/80">
              {new Date(previewRevision.created_at).toLocaleString()} · {previewRevision.username}
            </h3>
            <pre className="mt-3 whitespace-pre-wrap rounded-md bg-orange-light/20 p-3 font-mono text-xs leading-relaxed text-ink">
              {previewRevision.content}
            </pre>
            <button
              type="button"
              onClick={() => setPreviewRevision(null)}
              className="mt-3 w-full rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
            >
              닫기
            </button>
          </div>
        </div>
      )}

      {showLatestPreview && handTypedConflict && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setShowLatestPreview(false)}
        >
          <div
            className="max-h-[80vh] w-[32rem] overflow-y-auto rounded-lg bg-white p-5 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-sm font-medium text-ink/80">
              팀원이 저장한 최신{" "}
              {handTypedConflict.target === "content" ? "CLAUDE.md" : "Hooks"} 내용 (읽기 전용)
            </h3>
            <pre className="mt-3 whitespace-pre-wrap rounded-md bg-orange-light/20 p-3 font-mono text-xs leading-relaxed text-ink">
              {handTypedConflict.latestContent}
            </pre>
            <button
              type="button"
              onClick={() => setShowLatestPreview(false)}
              className="mt-3 w-full rounded-md border border-ink/15 bg-white px-3 py-1.5 text-sm text-ink transition hover:bg-orange-light/40"
            >
              닫기
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
