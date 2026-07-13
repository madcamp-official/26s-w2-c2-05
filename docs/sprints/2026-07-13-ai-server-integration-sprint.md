# AI 서버 ↔ 웹서버 연동 스프린트

**스프린트 목표**: 완성된 `ai_server`(`/analyze`, `/embed`)를 `web-server`에 붙여서,
DESIGN.md가 원래 그리던 핵심 기능 — **세션 JSONL 업로드 → 개인 추천(hook/CLAUDE.md)
→ 여러 팀원의 추천이 쌓이면 팀 공통 규칙으로 자동 승격 → CLAUDE.md에 반영** — 을
지금의 실제 `web-server` 구조(회원가입/JWT 인증, `Project`/`ProjectMember`,
"저장 버튼 + 변경 이력" 편집 플로우) 위에 실제로 동작하게 만든다.

**참고 문서**: `DESIGN.md`(제품/아키텍처 설계 전체), `ai_server/schemas.py`·`main.py`
(이미 확정된 `/analyze`·`/embed` 계약), `docs/superpowers/plans/2026-07-10-web-server-frontend.md`
(Task 3~7에 preprocessing/matching 참고 구현이 있음 — 단, 아래 "확정된 설계 결정"의
매핑에 맞게 고쳐서 재사용), `frontend/app/project/[id]/page.tsx`(현재 "세션 업로드"는
버튼만 있고 실제 제출은 안 되는 스텁 상태)

**워크플로우 원칙 적용** (`CLAUDE.md` 4절 기준):
- DESIGN.md 원본 스키마(`member_id`/`share_code`/localStorage UUID)와 지금 실제
  구현(`user_id`/JWT/username 초대)이 크게 달라서, 설계 결정을 먼저 문서화하고
  시작한다 (아래 "확정된 설계 결정" 참고 — Think Before Coding)
- 태스크마다 Red(실패 테스트)→Green(최소 구현)→Refactor
- 백엔드는 TDD, 프론트는 UI 구현 후 수동 확인 (기존 스프린트들과 동일 패턴)
- **개인 모드 먼저, 팀 모드는 그 위에 얹기** — DESIGN.md Next Steps 1~2번이 이미
  이 순서를 권장함("이게 팀 모드의 추출 단계이기도 하므로 선행 투자가 낭비되지
  않는다"). Skill 추천 타입(3번째 타입)은 DESIGN.md에서도 "두 타입 안정화 후"로
  미뤄뒀으므로 이번 스프린트도 hook/claude_md 두 타입만 다룬다.

---

## 확정된 설계 결정 (DESIGN.md 원본 스키마와의 차이)

| DESIGN.md 원본 | 실제로 쓸 것 | 이유 |
|---|---|---|
| `member_id`(localStorage UUID, 회원가입 없음) | 이미 있는 `user_id`(JWT 인증) | web-server가 이미 실계정 시스템으로 구현됨 — 되돌릴 이유 없음 |
| `team_id`(DESIGN.md 섹션 9 TODO에서 용어 불일치 지적) | 이미 있는 `project_id` | 팀 = 프로젝트 멤버십으로 이미 존재 |
| `POST /projects/{share_code}/join` (참여 코드) | 이미 있는 `POST /projects/{id}/invite`(username으로 owner가 초대) | 초대 방식이 이미 구현/스프린트 완료됨 — 중복 구현 안 함 |
| "임계값 넘으면 승인 없이 자동으로 md 파일에 반영" | **팀 추천이 승격되면 "적용" 버튼이 나타나고, 클릭하면 지금 편집 중인 `content` textarea에 병합됨 (그 다음 기존 "저장" 버튼을 눌러야 실제 커밋)** | 이미 "저장 버튼 + 변경 이력" 구조로 바꿔놨는데(2026-07-13 리비전 스프린트), 승인 없이 즉시 파일을 덮어쓰면 사용자가 타이핑 중이던 미저장 내용을 잃을 위험이 생김. 최소한의 승인 스텝(적용 클릭)을 추가 — DESIGN.md의 "자동 반영"이 뜻하는 "승인 UI 없이 웹 상태가 바로 바뀐다"는 원칙은 유지하되, 텍스트 덮어쓰기 안전장치만 더함 |
| Skill 추천(3번째 타입) | 범위 밖 | DESIGN.md 자체가 "두 타입 안정화 후" 순서를 권장 |
| GitHub 자동 push(승격 시 diff 미리보기 → 승인 → push) | 범위 밖(v2) | 이미 있는 수동 "PUSH" 버튼(현재 `content` 전체를 push)으로 충분 — 승격된 그룹 diff별 부분 push는 추가 복잡도 대비 이번 스프린트 가치가 낮음 |
| RPD 사전 차단 UX(잔여 RPD로 버튼 비활성화, 0되면 에러 페이지) | 범위 밖(단순화) | `/analyze`가 429를 주면 그 에러 메시지만 그대로 보여줌 — 사전 비활성화/전용 에러 페이지는 다음 스프린트 |

**DB**: 새 테이블만 추가(`Session`, `PersonalRecommendation`, `RecommendationGroup`,
`GroupMembership`) — 기존 `User`/`Project`/`ProjectMember`/`ProjectRevision`은
안 건드림. 마이그레이션 도구 없이 `SQLModel.metadata.create_all`(`init_db()`)로
충분 (Simplicity First, 기존 관례와 동일).

**웹서버 → AI서버 통신**: `web-server/ai_client.py`(신규) — `httpx.AsyncClient`로
`AI_SERVER_URL`(기본 `http://localhost:8001`, `.env`에 추가) 호출. AI서버는 절대
외부에 노출 안 하고 웹서버만 내부 호출 (DESIGN.md "배포 구조" 그대로).

---

## Day 1 — 웹서버 ↔ AI서버 연결 배관 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-01 | `.env`에 `AI_SERVER_URL` 추가 | `web-server/.env.example`·`.env`에 `AI_SERVER_URL=http://localhost:8001` 추가. | 10분 | 없음 | 값 존재 확인 |
| T-02 | `web-server/ai_client.py` — AI서버 HTTP 클라이언트 (Red→Green) | `analyze(pattern_summary, client=None) -> dict`, `embed(text, client=None) -> list[float]`. `httpx.MockTransport`로 스텁. 429는 `GeminiQuotaExceeded`, 그 외 실패는 `httpx.HTTPStatusError`로 전파(호출부에서 구분 처리). | 1.5시간 | T-01 | 테스트 3개: analyze 성공 파싱 / embed 성공 파싱 / 429 시 전용 예외 발생 |
| T-03 | `web-server/preprocessing.py` — 세션 JSONL 규칙 기반 전처리 (Red→Green) | `extract_pattern_summary(jsonl_text: str) -> str \| None`. Claude Code 세션 JSONL에서 반복되는 bash 커맨드(`tool_use`+`Bash`)와 유저 정정 발언(`type: user`, "아니/말고/대신/하지 마/다시" 키워드)을 추출, 3회 미만은 버림. **Task 착수 전 실제 세션 JSONL 샘플 하나로 필드명이 이 가정과 맞는지 대조할 것** — 다르면 이 함수 내부만 교체(인터페이스 고정이라 이후 태스크 영향 없음). | 2시간 | 없음(T-02와 병렬 가능) | 테스트 4개(반복 bash 커맨드 추출/반복 유저 정정 추출/임계값 미달 버림/malformed 라인 무시) — `docs/superpowers/plans/2026-07-10-web-server-frontend.md` Task 3의 테스트 케이스 재사용 가능 |
| T-04 | 전체 테스트 확인 | `pytest web-server/tests -v` 통과 확인. | 15분 | T-02, T-03 | 전체 PASS |

## Day 2 — 개인 추천 모델 + 업로드 오케스트레이션 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-05 | `Session`/`PersonalRecommendation` 모델 추가 | `web-server/models.py`: `Session`(id, project_id FK, user_id FK, uploaded_at, status: `processed`\|`no_patterns`\|`failed`, UNIQUE(project_id, user_id) — 재업로드 시 upsert), `PersonalRecommendation`(id, session_id FK, user_id FK, type, payload JSON 문자열, created_at). | 45분 | 없음 | 테이블 생성 확인 |
| T-06 | 세션 업로드 엔드포인트 (Red→Green) | `web-server/routers/sessions.py` 신규: `POST /projects/{project_id}/sessions` (multipart 파일 업로드, 10MB 상한). 프로젝트 멤버만 가능(403). 같은 (project, user) 재업로드 시 이전 `Session`+`PersonalRecommendation` 삭제 후 교체(upsert, DESIGN.md D7). `extract_pattern_summary` → `None`이면 Gemini 호출 없이 `status="no_patterns"` 반환. 패턴 있으면 `ai_client.analyze()` 호출 → 후보를 `PersonalRecommendation`으로 저장 후 응답에 포함. Gemini 429/503은 각각 429/503으로 그대로 패스스루(에러 메시지 표시, DESIGN.md 섹션12 TODO였던 예외처리 누락 이슈도 여기서 함께 해결). | 2.5시간 | T-02, T-03, T-05 | 테스트 4개: 패턴 있으면 개인 추천 반환 / 패턴 없으면 Gemini 호출 안 하고 `no_patterns` / 재업로드 시 이전 추천 교체(중복 안 됨) / AI서버 429 시 429로 전파 |
| T-07 | 개인 추천 조회 API | `GET /projects/{project_id}/recommendations/me` — 로그인한 유저 자신의 최신 `PersonalRecommendation` 목록. | 30분 | T-06 | 테스트: 본인 것만 보임, 다른 유저 것 안 섞임 |
| T-08 | 전체 테스트 확인 | `pytest web-server/tests -v`. | 15분 | T-07 | 전체 PASS |

## Day 3 — 팀 매칭 + 승격 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-09 | `RecommendationGroup`/`GroupMembership` 모델 | `web-server/models.py`: `RecommendationGroup`(id, project_id FK, type, representative_text, representative_vector JSON 문자열\|None, promoted bool, created_at, updated_at), `GroupMembership`(group_id FK, user_id FK, session_id FK, original_text, reason, confidence — PK(group_id, user_id)). | 45분 | T-05 | 테이블 생성 확인 |
| T-10 | 점진적 매칭 로직 (Red→Green) | `web-server/matching.py`: `normalize_command`, `cosine_similarity`(numpy), `match_hook_candidate(...)`(정규화된 command 문자열 완전 일치로 그룹 매칭), `match_claude_md_candidate(...)`(임베딩 코사인 유사도 ≥0.85로 매칭, `ai_client.embed()` 호출). 그룹 멤버 수가 **2명 이상**이면 `promoted=True` (DESIGN.md D4, 실제 2인팀 기준). 같은 유저 재업로드는 멤버 수 중복 카운트 안 됨. `docs/superpowers/plans/2026-07-10-web-server-frontend.md` Task 5의 검증된 로직을 `member_id`→`user_id`만 바꿔 재사용. | 2.5시간 | T-09 | 테스트 7개(기존 플랜 Task 5 테스트 세트 그대로: 1명이면 미승격/2명이면 승격/이벤트 다르면 별도 그룹/재업로드 중복 카운트 안 됨/유사도 기반 claude_md 그룹핑 등) |
| T-11 | 업로드 오케스트레이션에 매칭 연결 | T-06의 `POST /projects/{project_id}/sessions`가 개인 추천 저장 후 각 후보를 `match_hook_candidate`/`match_claude_md_candidate`에 통과시켜 팀 그룹도 함께 갱신. 응답에 `updated_team_groups`(갱신된 그룹의 id/type/representative_text/affected_members/promoted) 포함. | 1시간 | T-10 | 테스트: 2번째 팀원 업로드 시 응답에 `promoted: true`인 그룹이 포함됨 |
| T-12 | 팀 추천(승격된 것만) 조회 API | `GET /projects/{project_id}/recommendations/team` — `promoted=True`인 그룹만, 근거(`GroupMembership`의 `original_text`/몇 명인지) 포함. 프로젝트 멤버만 접근 가능. | 45분 | T-11 | 테스트: 승격 전엔 빈 배열, 승격 후 근거와 함께 나옴 |
| T-13 | 전체 테스트 확인 | `pytest web-server/tests -v`. | 15분 | T-12 | 전체 PASS |

## Day 4 — 프론트엔드 연동 (UI 구현 후 수동 확인)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-14 | `lib/projects.ts`에 함수 추가 | `uploadSession(projectId, file)`(multipart POST), `getMyRecommendations(projectId)`, `getTeamRecommendations(projectId)`. 타입(`PersonalRecommendation`, `TeamRecommendation`) 정의. | 45분 | T-07, T-12 | `npx tsc --noEmit` 통과 |
| T-15 | "세션 업로드" 버튼을 실제 제출로 교체 | 기존 스텁(`disabled`, 파일 선택만 되고 제출 안 됨)을 실제 업로드로 바꿈. 업로드 중 로딩 상태, 실패 시(429/503/no_patterns 등) 메시지 표시, 성공 시 개인/팀 추천 목록 갱신. | 1.5시간 | T-14 | 파일 올리면 실제로 API 호출되고 결과 반영되는지 수동 확인 |
| T-16 | 개인 추천 카드 UI | aside에 "내 추천" 섹션 추가 — 이전에 있던 "추천(예시)" 정적 카드 UI를 실제 데이터로 되살림(hook/claude_md 타입별 카드, "적용하기" 클릭 시 `content` textarea에 append). | 1.5시간 | T-15 | 적용하기 누르면 textarea에 반영되고, "저장"을 눌러야 실제 커밋되는지 확인 |
| T-17 | 팀 추천(승격된 것) UI | aside에 "팀 추천" 섹션 추가 — "N명에게서 나온 규칙" 근거와 함께 표시, "적용하기"는 개인 추천과 동일하게 textarea에 병합. | 1시간 | T-15 | 2계정으로 업로드해서 2번째 업로드 후 팀 추천이 뜨는지 수동 확인 |
| T-18 | 검증 + 마무리 | `npx tsc --noEmit`, 백엔드 `pytest` 전체, 브라우저에서 2계정으로 전체 시나리오(업로드→개인 추천→적용→저장, 2번째 계정 업로드→팀 추천 승격) 수동 확인. `/simplify`로 과설계 없는지 확인. | 1시간 | T-16, T-17 | 타입체크+테스트 통과, 수동 시나리오 통과 |

---

## 이번 스프린트에서 다루지 않는 것 (명시적으로 범위 밖)

- **Skill 추천 타입** — DESIGN.md 자체가 두 타입 안정화 후로 미룸
- **GitHub 자동 push(승격 diff별 미리보기→승인→push)** — 기존 수동 PUSH 버튼으로 대체
- **RPD 사전 차단 UX**(잔여 RPD 노출, 0되면 전용 에러 페이지) — 429 에러 메시지만 표시
- **hooks(`settings.json`) 병합 다운로드/표시** — 이번엔 CLAUDE.md(`content`)만 다룸, hook 후보는 저장은 되지만 UI에 별도 "다운로드" 없음. 필요해지면 다음 스프린트
- **그룹 대표값 재계산**(DESIGN.md TODO 섹션4 — 최초 멤버 값 고정 문제), **상충하는 취향 처리**, **재업로드 시 그룹 멤버십 자동 이탈** — DESIGN.md에도 미해결로 남아있던 TODO, 이번 스프린트 스코프 아님
- **로컬 스크립트로 JSONL 경로 자동탐색** — 지금 안내 문구(`~/.claude/projects/...`)로 충분, 별도 스크립트 배포는 다음 스프린트
