# 저장 충돌 방지 스프린트

**스프린트 목표**: 여러 팀원이 같은 프로젝트의 CLAUDE.md/Hooks를 동시에 편집하다가
한쪽이 저장(reload 전)한 뒤 다른 쪽이 그 사실을 모른 채 저장을 눌러 서로의 변경사항을
덮어쓰는 문제를 해결한다. 이미 연결돼 있는 실시간 접속 웹소켓(`/ws/projects/{id}`)을
활용해 **저장 버튼을 누르기 전에 미리 최신 내용을 합쳐두는 예방책**을 메인으로 하고,
`updated_at` 기반 낙관적 락을 최후 안전망으로 둔다.

**참고 문서**: `CLAUDE.md`(스프린트 워크플로우), `docs/sprints/2026-07-13-invite-presence-sprint.md`
(웹소켓 `ConnectionManager` 최초 도입 스프린트), `docs/sprints/2026-07-14-hooks-separation-sprint.md`
(로컬 `app.db` 수동 마이그레이션 절차 선례), `web-server/routers/projects.py`,
`web-server/routers/presence.py`, `frontend/app/project/[id]/page.tsx`

**워크플로우 원칙 적용** (`CLAUDE.md` 4절 기준): 백엔드는 TDD(Red→Green), 프론트는
UI 구현 후 수동 확인 (이 저장소에 프론트 테스트 러너가 아직 설치돼 있지 않음 — 기존
스프린트들도 전부 이 패턴). GitHub 토큰과 무관하므로 `/security-review` 필수 게이트
대상은 아님.

---

## 확정된 설계 결정

대화로 여러 대안(즉시 커밋형 적용, 사후 409 병합, 완전 자동 3-way merge/CRDT)을
검토한 뒤 아래로 확정함 — 근거는 "기존 UX(추천 모아 적용→저장) 유지 + 효과 대비
구현 범위".

| 항목 | 결정 | 근거 |
|---|---|---|
| 메인 장치 | 저장 성공 시 웹소켓으로 `content_updated` 이벤트(신호만, 전체 내용 아님)를 같은 프로젝트 접속자에게 broadcast. 받은 클라이언트는 저장 누르기 전이면 자동으로 최신 내용을 다시 불러와 자신의 pending 추천 변경사항을 그 위에 재적용(replay)해 둔다. | 추천 카드로 생긴 변경은 어떤 텍스트가 추가됐는지 정확히 알고 있어(`formatClaudeMdCandidate`/`mergeHookIntoJson`) 안전하게 재현 가능. 대부분의 충돌을 저장 시도 전에 미리 없앨 수 있음 |
| 안전망 | `Project.updated_at` 컬럼 + 저장 요청에 `expected_updated_at`(선택 필드) 추가. 값이 오고 서버의 현재 `updated_at`과 다르면 409, 저장 안 함. | 웹소켓 이벤트 전달 지연 등으로 인한 수백ms 내 동시 저장까지는 예방책이 못 막으므로 최후 방어선. 필드를 **선택(optional)**으로 둬서 기존 테스트/호출부를 건드리지 않음(안 보내면 기존처럼 무조건 덮어쓰기) |
| 손으로 직접 타이핑한 경우 | textarea에 직접 입력해서, "마지막으로 불러온 원본 + pending 추천 replay" 결과와 현재 로컬 content가 다르면 자동 병합하지 않고 배너 + "최신 내용 보기"만 제공(기존 `previewRevision` 모달 패턴 재사용) | 자유 텍스트끼리 자동 merge는 위험 — 이번 스코프에서는 사람이 보고 판단하게 함(초보 개발자 타겟이라 실제로는 드문 경로) |
| 실패 시 정합성 | **(2026-07-14 수정)** `reconcileWithServer`(재조회+replay+"팀원이 저장했어요" 안내)는 진짜 충돌(`SaveConflictError`, 409)일 때만 탄다. JSON 형식 오류(400)나 네트워크 오류 등 그 외 실패는 그냥 `setError`로 원인 메시지만 보여주고 끝 — 실제로 아무도 저장한 적 없는데 "팀원이 방금 저장했어요" 배너가 뜨는 오탐을 막기 위함 | 최초엔 "실패 유형 안 가리고 다 병합 흐름"으로 갔었는데, 손타이핑한 JSON이 유효하지 않아 400이 났을 때도 팀원 충돌처럼 잘못 안내되는 버그로 이어져서 수정함 |
| DB 마이그레이션 | `SQLModel.metadata.create_all()`은 기존 테이블에 컬럼을 안 붙이므로, 로컬 `app.db`에 `ALTER TABLE projects ADD COLUMN updated_at ...`을 한 번 수동 실행 | hooks-separation 스프린트에서 쓴 것과 동일한 절차, 새 마이그레이션 도구 도입 안 함(Simplicity First) |

---

## Day 1 — 백엔드: `updated_at` 낙관적 락 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-01 | `Project.updated_at` 컬럼 추가 | `web-server/models.py`: `Project`에 `updated_at: datetime = Field(default_factory=datetime.utcnow)` 추가. | 15분 | 없음 | 테이블 생성 확인 |
| T-02 | `ProjectOut`에 `updated_at` 포함 (Red→Green) | `web-server/routers/projects.py`: `ProjectOut`에 `updated_at: datetime` 추가, `_to_project_out`에서 `_as_utc(project.updated_at)`로 채움(기존 `created_at` 처리와 동일 패턴). | 30분 | T-01 | 테스트: 프로젝트 생성/조회 응답에 `updated_at`이 tz-aware(`Z`/`+00:00`)로 포함됨 |
| T-03 | `expected_updated_at` 낙관적 락 (Red→Green) | `UpdateContentRequest`/`UpdateHooksRequest`에 `expected_updated_at: datetime \| None = None` 추가. `update_project_content`/`update_project_hooks`에서 이 값이 있고 `_as_utc(project.updated_at)`와 다르면 `HTTPException(409, detail="다른 팀원이 먼저 저장했어요")`, 저장 스킵. 값이 없으면(기존 호출부 그대로) 지금처럼 무조건 저장. | 1.5시간 | T-02 | 테스트 4개: (1) `expected_updated_at` 없이 저장 → 기존처럼 200 (2) 최신 `updated_at`을 보내면 200 (3) 오래된(stale) `updated_at`을 보내면 409, DB 내용 안 바뀜 (4) hooks 엔드포인트도 동일하게 동작 |
| T-04 | 저장 성공 시 `updated_at` 갱신 확인 | 저장 성공 시 `project.updated_at = datetime.utcnow()`로 갱신되고 응답에 새 값이 오는지. | 30분 | T-03 | 테스트: 저장 전후 `updated_at`이 달라짐 |
| T-05 | 로컬 `app.db` 마이그레이션 | `pytest web-server/tests -v` 전체 통과 확인 후, 실행 중인 `web-server/app.db`에 `ALTER TABLE projects ADD COLUMN updated_at DATETIME` 수동 실행 + 기존 row는 `UPDATE projects SET updated_at = created_at WHERE updated_at IS NULL`로 백필. | 20분 | T-04 | 전체 PASS + 로컬 서버 재기동 후 기존 프로젝트 조회 시 에러 없음 |

## Day 2 — 백엔드: 웹소켓 저장 이벤트 브로드캐스트 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-06 | `ConnectionManager.broadcast_content_updated` (Red→Green) | `web-server/routers/presence.py`: `ConnectionManager`에 `async def broadcast_content_updated(self, project_id: str, target: str, updated_by: str) -> None` 추가 — 해당 프로젝트 접속자 전원에게 `{"type": "content_updated", "target": target, "updated_by": updated_by}` send_json (기존 `_broadcast`의 `online_users` 메시지와 별개 타입). | 1시간 | 없음 | `test_presence.py` 패턴처럼 `websocket_connect` 2개 열고, 한쪽에서 메서드 호출 시 다른 쪽이 해당 이벤트를 받는지 pytest로 확인 |
| T-07 | 저장 성공 시 브로드캐스트 연결 | `web-server/routers/projects.py`: `from .presence import manager` 추가. `update_project_content`/`update_project_hooks`를 `async def`로 전환(이미 `onboard_project`가 같은 파일에서 동기 DB 호출을 async def 안에 쓰는 선례 있음), 커밋 후 `await manager.broadcast_content_updated(project_id, target="content"/"hooks", updated_by=user.username)` 호출. | 1시간 | T-06 | 테스트: 저장 API 호출 시 같이 연결된 다른 클라이언트의 웹소켓에 이벤트가 오는지(TestClient로 websocket 열어두고 PUT 호출 후 receive_json 확인) |
| T-08 | 전체 pytest 확인 | `pytest web-server/tests -v`. | 15분 | T-07 | 전체 PASS |

## Day 3 — 프론트: 웹소켓 이벤트 수신 + 자동 병합 (UI 구현 후 수동 확인)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-09 | `lib/projects.ts` 확장 | `Project` 타입에 `updated_at: string` 추가. `saveProjectContent(id, content, expectedUpdatedAt?)`/`saveProjectHooks(id, hooksContent, expectedUpdatedAt?)`가 body에 `expected_updated_at`을 같이 보내도록 확장. 응답이 409면 구분 가능하도록 `export class SaveConflictError extends Error {}`를 던짐(다른 에러는 기존처럼 일반 `Error`). | 45분 | Day 1 | `npx tsc --noEmit` 통과 |
| T-10 | WebSocket을 `useRef`로 전환 | `frontend/app/project/[id]/page.tsx`: `wsRef = useRef<WebSocket \| null>(null)`로 소켓 연결은 한 번만(마운트 시) 만들고, `onmessage` 핸들러는 별도 `useEffect`(deps: `pendingAppliedPersonalIds`, `pendingAppliedGroupIds`, `personalRecs`, `teamRecs`, `project`)에서 매번 최신 값으로 재바인딩. `data.online_users`면 기존처럼 처리, `data.type === "content_updated"`면 T-11의 병합 함수 호출. | 1시간 | T-09 | 브라우저 콘솔에서 두 탭으로 접속 시 여전히 접속자 목록이 정상 동작(회귀 없음) |
| T-11 | 병합/재조회 헬퍼 `reconcileWithServer` | `getProject`로 최신 프로젝트를 받아온 뒤, pending 추천들을 그 위에 replay(`applyPersonalRecommendation`/`applyTeamRecommendation`에서 쓰는 append/merge 로직 재사용). "손으로 타이핑했는지"는 `현재 로컬 content !== (마지막으로 불러온 project.content에 pending 추천만 replay한 결과)`로 판별 — 다르면 자동 병합 대신 배너만 노출. | 2시간 | T-10 | 시나리오: A가 추천 적용만 하고 저장 안 한 상태에서 B가 저장 → A 화면이 자동으로 B의 최신 내용 + A의 pending 추천으로 합쳐짐(수동 확인) |
| T-12 | `handleSave`에 실패 처리 연결 | 저장 API가 실패(네트워크 오류 또는 `SaveConflictError`) 하면 catch에서 `reconcileWithServer` 호출 + "다른 팀원이 먼저 저장했어요. 최신 내용에 회원님의 변경사항을 다시 합쳤어요. 저장을 다시 눌러주세요" 안내, 이번 저장 시도는 중단(추천 적용 API 호출까지 진행 안 함). | 45분 | T-11 | 시나리오: 거의 동시에 두 탭에서 저장 시도 → 늦은 쪽이 409를 받고 자동 병합 후 안내, 재시도하면 성공(수동 확인) |
| T-13 | 손 타이핑 감지 시 배너 + 미리보기 | T-11에서 자동 병합이 보류된 경우, 기존 `previewRevision` 모달(759~783행)과 같은 패턴으로 "최신 서버 내용 보기" 모달 추가(읽기 전용). | 1시간 | T-11 | 시나리오: textarea에 직접 타이핑 후 팀원이 저장 → 자동으로 안 덮어써지고 배너/미리보기로만 안내되는지 확인 |
| T-14 | 검증 + 마무리 | `npx tsc --noEmit`, 백엔드 `pytest` 전체, 브라우저 두 탭으로 T-11/T-12/T-13 시나리오 전부 수동 확인. `/simplify`로 과설계 없는지 확인. | 1시간 | T-13 | 타입체크+테스트 통과, 세 시나리오 모두 통과 |

---

## 이번 스프린트에서 다루지 않는 것 (명시적으로 범위 밖)

- **완전 자동 3-way 텍스트 merge / OT / CRDT** — 손 타이핑 충돌은 사람이 보고 판단(배너+미리보기)하는 선에서 마무리. 실사용 중 자주 문제 되면 재검토
- **웹소켓 자기 자신의 저장 echo 스킵 최적화** — 내가 방금 저장한 이벤트가 나에게도 돌아와 `reconcileWithServer`가 한 번 더 도는 건 멱등(같은 내용 재조회)이라 해가 없음. `user_id` 비교로 스킵하는 최적화는 이번엔 안 함
- **다중 서버 프로세스 간 웹소켓 상태 공유(Redis pub/sub)** — invite-presence 스프린트 때와 동일하게 단일 프로세스 in-memory로 충분
- **Alembic 등 마이그레이션 도구 도입** — 이전 스프린트들과 동일하게 로컬 `app.db`는 수동 `ALTER TABLE` 1회 실행으로 충분