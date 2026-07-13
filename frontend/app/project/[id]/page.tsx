"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  getProject,
  saveProjectContent,
  setGithubRepo,
  pushToGithub,
  inviteMember,
  listRevisions,
  getRevision,
  type Project,
  type Revision,
  type RevisionDetail,
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

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | undefined>();
  const [content, setContent] = useState("");
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
  const [sessionFile, setSessionFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [previewRevision, setPreviewRevision] = useState<RevisionDetail | null>(null);
  const sessionFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    const ws = new WebSocket(`ws://localhost:8000/ws/projects/${projectId}?token=${token}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setOnlineUsers(data.online_users ?? []);
    };

    return () => {
      ws.close();
      setOnlineUsers([]);
    };
  }, [projectId]);

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
        setRepoInput(p.github_repo ?? "");
      })
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  useEffect(() => {
    listRevisions(projectId)
      .then(setRevisions)
      .catch((err) => setError((err as Error).message));
  }, [projectId]);

  async function handleSave() {
    setError(null);
    setSaving(true);
    try {
      const updated = await saveProjectContent(projectId, content);
      setProject(updated);
      const latest = await listRevisions(projectId);
      setRevisions(latest);
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

  function handleDownload() {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "CLAUDE.md";
    a.click();
    URL.revokeObjectURL(url);
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
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">
            {project?.name ?? "프로젝트"}
          </h1>
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
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
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

          <label className="mb-2 mt-10 block text-sm font-medium text-ink/70">
            CLAUDE.md 내용을 수정 후 저장을 눌러주세요
          </label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            spellCheck={false}
            className="h-[420px] w-full resize-none rounded-lg border border-ink/10 bg-white p-4 font-mono text-sm leading-relaxed text-ink shadow-sm focus:border-orange focus:outline-none focus:ring-2 focus:ring-orange/30"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "저장 중..." : "저장"}
            </button>
            <button
              onClick={handleDownload}
              className="rounded-md border border-ink/15 bg-white px-4 py-2 text-sm font-medium text-ink transition hover:bg-orange-light/40"
            >
              다운로드
            </button>
            <button
              type="button"
              onClick={handlePush}
              disabled={pushing}
              className="ml-auto rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pushing ? "PUSH 중..." : pushed ? "PUSH 완료" : "PUSH"}
            </button>
          </div>
        </section>

        <aside>
          <div className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-sm font-medium text-ink/70">세션 업로드</h2>
            <input
              ref={sessionFileInputRef}
              type="file"
              accept=".jsonl"
              onChange={(e) => setSessionFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => sessionFileInputRef.current?.click()}
              className="w-full rounded-md bg-orange px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-dark"
            >
              {sessionFile ? `${sessionFile.name} 업로드` : "업로드"}
            </button>
            <p className="mt-3 text-xs leading-relaxed text-ink/50">
               <code className="rounded bg-orange-light/40 px-1">C:\Users\(username)\.claude\projects\
              </code>
              <br />
              세션 JSONL 파일은 위 링크 폴더안, 이 프로젝트 경로에 해당하는 하위 폴더에 있어요. 그중 가장 최근에 수정된 파일을 선택해주세요.
            </p>
          </div>

          <div className="mt-6 rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
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
                      className="w-full rounded-md px-2 py-1.5 text-left text-sm text-ink/70 transition hover:bg-orange-light/40"
                    >
                      {new Date(r.created_at).toLocaleString()} · {r.username}
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
    </main>
  );
}
