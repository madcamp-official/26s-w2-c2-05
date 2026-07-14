# CLAUDE.md / Hooks 분리 스프린트

**스프린트 목표**: 지금은 AI서버가 주는 `claude_md` 타입 후보와 `hook` 타입 후보를
"적용하기" 누르면 **둘 다 `Project.content`(CLAUDE.md 텍스트)에 마크다운 줄로
섞여 들어가고** 있어서, hook 추천이 실제 Claude Code가 읽는 형식(`.claude/settings.json`의
`hooks` 키)으로는 전혀 반영되지 않는다. 이번 스프린트에서 **CLAUDE.md와 Hooks를
완전히 분리된 저장소/편집 UI/PUSH 대상**으로 만든다.

**참고 문서**: `web-server/routers/sessions.py`(추천 적용 로직), `web-server/routers/projects.py`
(`content` 저장/PUSH), `frontend/app/project/[id]/page.tsx`, `web-server/github_client.py`
(`push_file` — 그대로 재사용)

**워크플로우 원칙 적용** (`CLAUDE.md` 4절 기준): 백엔드는 TDD, 프론트는 UI 구현 후
수동 확인 (기존 스프린트들과 동일 패턴).

---

## 확정된 설계 결정

| 항목 | 결정 | 근거 |
|---|---|---|
| PUSH 시 hooks 파일 처리 | `.claude/settings.json`을 **통째로 덮어쓰기** (기존 `github_client.push_file`을 CLAUDE.md와 동일하게 재사용) | 사용자 판단: 프로젝트를 처음 만들 때는 레포에 기존 settings.json이 없는 경우가 대부분이라, 병합(GET→JSON parse→hooks 키만 교체→PUT) 로직을 추가하는 복잡도가 이번 스코프 대비 안 맞음. CLAUDE.md push와 완전히 같은 패턴이라 구현/이해 비용도 최소화됨 |
| hooks 편집 UI | CLAUDE.md와 동일한 **raw JSON textarea** (직접 편집 + 저장 버튼 + 변경 이력) | 이미 검증된 패턴(저장 버튼 시점에만 커밋, 리비전 히스토리) 재사용 — 새 UI 패턴 발명 안 함 |
| DB 저장 위치 | `Project`에 `hooks_content: str` 컬럼 추가 (기본값은 `{"hooks": {}}` pretty-print) | `content`(CLAUDE.md)와 대칭 구조 — 별도 테이블 불필요 |
| 변경 이력 | 기존 `ProjectRevision`에 `target: str`("content"\|"hooks") 컬럼만 추가해서 재사용 | 리비전 목록/상세/미리보기 API·UI를 전부 새로 만들 필요 없이 필터 하나만 추가하면 됨 (Simplicity First) |
| hook 후보 "적용하기" 시 저장 형태 | 텍스트 줄 append가 아니라, `hooks_content`의 JSON을 **파싱해서 실제 hook 항목으로 merge** (`{"hooks": {"<event>": [{"matcher": "<matcher>", "hooks": [{"type": "command", "command": "<command>"}]}]}}` 형태) | 이게 이번 스프린트의 핵심 목적 — "적용"이 실제로 Claude Code가 읽을 수 있는 유효한 hooks 설정이 되어야 함 |
| DESIGN.md와의 차이 | DESIGN.md가 원래 그리던 `GET /projects/{id}/hooks`(승격된 팀 그룹에서 자동 병합된 hooks JSON을 읽기 전용으로 제공)는 이번 결정으로 대체됨 — 대신 유저가 raw JSON을 직접 편집하고, 추천 "적용하기"는 그 JSON에 항목을 merge하는 보조 수단 | 이미 CLAUDE.md content도 "자동 반영" 대신 "적용하기+저장" 방식으로 간 것과 일관성 유지 |

**DB 마이그레이션**: 새 컬럼만 추가(`Project.hooks_content`, `ProjectRevision.target`) —
`SQLModel.metadata.create_all()`은 기존 테이블에 컬럼을 안 붙여주므로, 로컬 `app.db`에는
지난번처럼 `ALTER TABLE`을 수동으로 한 번 더 돌려야 함 (Day 1 마지막에 실행).

---

## Day 1 — 백엔드: hooks 저장 + 리비전 분리 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-01 | `Project.hooks_content` 컬럼 추가 | `web-server/models.py`: `Project`에 `hooks_content: str = Field(default=DEFAULT_HOOKS)` — `DEFAULT_HOOKS = '{\n  "hooks": {}\n}'`. | 20분 | 없음 | 테이블 생성 확인 |
| T-02 | `ProjectRevision.target` 컬럼 추가 | `ProjectRevision`에 `target: str = Field(default="content")` 추가 — 기존 row는 전부 `"content"`로 채워짐(기본값). | 20분 | 없음 | 테이블 생성 확인 |
| T-03 | `ProjectOut`에 `hooks_content` 포함 (Red→Green) | `web-server/routers/projects.py`의 `ProjectOut`/`_to_project_out`에 `hooks_content` 추가 — `create_project`/`get_project`/`update_project_content`/`set_github_repo` 응답에 전부 포함되는지 확인. | 30분 | T-01 | 테스트: 프로젝트 생성 응답에 `hooks_content` 기본값이 들어있음 |
| T-04 | `PUT /projects/{project_id}/hooks` (Red→Green) | 새 엔드포인트: 멤버만 가능(403), body `{hooks_content: str}`가 **유효한 JSON이 아니면 400**(`json.loads` 실패 시), 유효하면 `project.hooks_content` 갱신 + `ProjectRevision(target="hooks")` 생성. `update_project_content`(기존 content 저장)와 거의 동일한 구조. | 1.5시간 | T-01, T-02 | 테스트 4개: 저장 성공/멤버 아니면 403/유효하지 않은 JSON이면 400/저장 시 리비전 생성됨 |
| T-05 | 리비전 목록에 `target` 필터 추가 (Red→Green) | `GET /projects/{project_id}/revisions?target=content\|hooks`(기본값 `content`, 기존 프론트 호출 그대로 호환) — 해당 target인 리비전만 최신순 반환. `GET .../revisions/{id}`(단건)는 target 구분 없이 그대로(이미 있는 그 리비전의 `content` 텍스트를 반환하는 것뿐이라 변경 불필요). | 1시간 | T-02, T-04 | 테스트: `target=hooks`로 조회하면 hooks 리비전만, `target=content`(또는 생략)면 content 리비전만 나옴 |
| T-06 | 전체 테스트 확인 + 로컬 `app.db` 마이그레이션 | `pytest web-server/tests -v` 통과 확인 후, 실행 중인 `app.db`에 `ALTER TABLE projects ADD COLUMN hooks_content ...`, `ALTER TABLE project_revisions ADD COLUMN target ...` 수동 실행(지난 스프린트와 동일 절차). | 30분 | T-05 | 전체 PASS + 로컬 서버에서 신규 API 정상 응답 확인 |

## Day 2 — 백엔드: PUSH가 CLAUDE.md + hooks 둘 다 반영 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-07 | PUSH 시 hooks도 함께 push (Red→Green) | `web-server/routers/projects.py`의 `push_to_github`: 기존 `CLAUDE.md` push에 이어 `github_client.push_file(..., path=".claude/settings.json", content=project.hooks_content, ...)` 추가 호출. `hooks_content`가 유효하지 않은 JSON이면 push 자체를 400으로 막음(깨진 JSON을 레포에 올리지 않기 위함). | 1.5시간 | Day 1 전체 | 테스트 3개: PUSH 시 `push_file`이 2번(CLAUDE.md, settings.json) 호출됨(mock으로 검증) / hooks JSON이 깨져있으면 400, push_file 호출 안 됨 / 기존 CLAUDE.md-only 동작(레포 미설정 등) 회귀 없음 |
| T-08 | 전체 테스트 확인 | `pytest web-server/tests -v`. | 15분 | T-07 | 전체 PASS |

## Day 3 — 프론트: CLAUDE.md / Hooks 탭 분리 (UI 구현 후 수동 확인)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-09 | `lib/projects.ts` 함수/타입 추가 | `Project.hooks_content` 추가, `saveProjectHooks(id, hooksContent)`, `listRevisions(id, target?)`로 시그니처 확장. | 30분 | Day 1, 2 | `npx tsc --noEmit` 통과 |
| T-10 | section(왼쪽)을 `CLAUDE.md`/`Hooks` 탭으로 분리 | 지금 있는 "My"/"Team" 탭(우측 추천 카드)과 같은 스타일로, **좌측 section 위쪽**에 `CLAUDE.md`/`Hooks` 탭 추가. 탭에 따라 textarea가 `content`/`hooksContent` state를 바인딩. "저장" 버튼은 활성 탭에 맞춰 `saveProjectContent`/`saveProjectHooks` 호출. | 1.5시간 | T-09 | 탭 전환 시 textarea 내용이 바뀌고, 각 탭에서 저장하면 해당 값만 갱신되는지 수동 확인 |
| T-11 | "변경 이력" 박스가 활성 탭을 따라감 | 좌측이 `CLAUDE.md` 탭이면 `target=content` 리비전을, `Hooks` 탭이면 `target=hooks` 리비전을 보여줌 (같은 박스, 데이터만 전환). | 1시간 | T-10 | Hooks 탭에서 저장한 리비전이 CLAUDE.md 리비전 목록에 안 섞이는지 확인 |
| T-12 | PUSH 버튼 안내 문구 갱신 | PUSH 버튼 옆/근처에 "CLAUDE.md + Hooks 둘 다 반영됩니다" 같은 짧은 안내 추가(선택, 사용자 혼란 방지용). | 15분 | T-07 | 문구 노출 확인 |

## Day 4 — 프론트: 추천 적용 로직 타입별 분리 (UI 구현 후 수동 확인)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-13 | hook 후보 "적용하기" → hooksContent JSON에 merge | `applyPersonalRecommendation`/`applyTeamRecommendation`을 타입별로 분리: `type==="claude_md"`는 기존처럼 `content`에 텍스트 append. `type==="hook"`은 `hooksContent`를 JSON.parse → `hooks[event]` 배열에서 같은 `matcher` 항목을 찾아 `command`를 추가(없으면 새 matcher 항목 생성) → 다시 JSON.stringify(pretty)해서 `hooksContent` state에 반영. 파싱 실패 시(유저가 직접 수정하다 깨뜨린 경우) 에러 메시지로 안내하고 merge 중단. | 2시간 | T-10 | hook 카드 "적용하기" 누르면 Hooks 탭 textarea의 JSON에 새 항목이 정확한 형식으로 추가되는지 수동 확인 (중복 matcher는 새로 안 늘어나고 기존 항목에 command만 추가되는지도 확인) |
| T-14 | 적용 대기 상태(pending) 분리 | 지금 "저장" 누를 때 `pendingAppliedPersonalIds`/`pendingAppliedGroupIds`를 한꺼번에 처리하는데, hook 타입 추천이 적용 대기 중이면 **Hooks 탭 저장 시에도** 함께 커밋되도록 확인(현재 구조상 이미 프로젝트 전체 "저장" 흐름에 안 걸려있고 개별 apply API 호출이라 큰 변경 없을 가능성 높음 — 실제 확인만). | 30분 | T-13 | hook 추천 적용 후 Hooks 탭에서 저장하면 해당 개인/팀 추천이 "반영됨"으로 바뀌는지 확인 |
| T-15 | 검증 + 마무리 | `npx tsc --noEmit`, 백엔드 `pytest` 전체, 브라우저에서 전체 시나리오(hook 후보 적용→Hooks 탭 JSON 확인→저장→PUSH→GitHub 레포에 `.claude/settings.json` 실제로 올라가는지) 수동 확인. `/simplify`로 과설계 없는지 확인. | 1시간 | T-14 | 타입체크+테스트 통과, 수동 시나리오 통과 |

---

## 이번 스프린트에서 다루지 않는 것 (명시적으로 범위 밖)

- **hooks 구조화 편집 UI**(이벤트/매처별 폼, 드래그앤드롭 등) — raw JSON textarea로 충분, 나중에 필요해지면 별도 스프린트
- **`.claude/settings.json` 병합 push**(레포에 이미 있는 설정 보존) — 이번엔 통째로 덮어쓰기로 확정, 실사용 중 문제 되면 재검토
- **skill 타입 추천** — 이전 스프린트부터 계속 범위 밖으로 유지
- **hooks JSON 스키마 검증**(유효한 JSON인지만 확인, `event`/`matcher` 값이 Claude Code가 허용하는 값인지까지는 검증 안 함) — AI서버(`ai_server/schemas.py`)가 이미 어느 정도 강제하고 있어서 이중 검증 비용 대비 효과가 낮다고 판단
