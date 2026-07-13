# CLAUDE.md 변경 이력 스프린트

**스프린트 목표**: CLAUDE.md 내용을 **자동저장 대신 명시적 "저장" 버튼**으로 저장하도록
바꾸고, 저장할 때마다 스냅샷을 남겨서 프로젝트 페이지 우측 `aside`의 "세션 업로드"
박스 아래에 "언제 · 누가 저장했는지" 변경 이력 목록을 보여준다. 항목을 클릭하면
그 시점의 CLAUDE.md 전체 내용을 모달로 미리 볼 수 있다.

**참고 문서**: `CLAUDE.md`(스프린트 워크플로우), `frontend/app/project/[id]/page.tsx`,
`web-server/models.py`, `web-server/routers/projects.py`

**워크플로우 원칙 적용** (`CLAUDE.md` 4절 기준):
- 설계 결정은 이미 사용자와 확정(아래 "확정된 설계 결정" 참고) — 코드 짜기 전에 문서화만 하면 됨
- 태스크마다 Red(실패 테스트)→Green(최소 구현)→Refactor 사이클 준수
- 각 태스크 끝날 때 요구사항/에러 없음 확인 (verification-before-completion)
- 프론트 vitest 인프라는 여전히 없음 — 이전 스프린트(초대/접속 현황)와 동일하게
  **백엔드는 TDD, 프론트는 UI 구현 후 수동 확인**으로 진행 (사용자 확인, 반복 적용)

---

## 확정된 설계 결정

- **저장 방식 전환**: 기존 500ms 디바운스 자동저장(`useEffect` + `lastSavedContent`
  ref, `page.tsx:76-86`)을 **제거**하고, 명시적 "저장" 버튼 클릭 시에만
  `PUT /projects/{id}`를 호출하도록 바꾼다. 저장 버튼을 누르기 전까지 로컬
  `content` state 변경은 서버에 반영되지 않는다.
- **리비전 기록 단위**: 저장 버튼이 눌려서 `PUT /projects/{id}`가 성공할 때마다
  그 시점의 **content 전체 스냅샷**을 새 리비전 레코드로 남긴다(디바운스 없이
  매 저장 = 1 리비전, 중복 제거 로직 없음 — 이제는 사용자의 명시적 액션이라
  자동저장 때와 달리 레코드 폭증 걱정이 없음).
- **표시 수준**: 목록에는 **시각 + 저장한 사용자의 username**만 보여준다
  (diff 계산은 이번 스프린트 범위 밖). 항목 클릭 시 모달로 그 리비전의 content
  전체를 읽기 전용으로 보여준다(복원 기능은 범위 밖 — 미리보기만).
- **DB 마이그레이션**: 별도 마이그레이션 도구 없이 `SQLModel.metadata.create_all`
  (기존 `db.py`의 `init_db()`)이 새 테이블을 자동으로 만들어주므로, 서버
  재시작만으로 충분 (Simplicity First — 기존 테이블 구조는 안 건드림).

---

## Day 1 — 백엔드 (TDD)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-01 | `ProjectRevision` 모델 추가 | `web-server/models.py`에 `ProjectRevision` 테이블 추가: `id`(uuid, PK), `project_id`(FK), `user_id`(FK), `content`(str, 스냅샷 전체), `created_at`. | 30분 | 없음 | 모델 임포트/테이블 생성 확인 (기존 `tests/conftest.py`의 `StaticPool` 픽스처로 생성되는지) |
| T-02 | 저장 시 리비전 자동 생성 (Red→Green) | `web-server/routers/projects.py`의 `update_project_content`(`PUT /projects/{id}`)가 content 저장과 **같은 트랜잭션**에서 `ProjectRevision` row도 함께 커밋하도록 수정. | 1시간 | T-01 | 테스트: PUT 호출 후 `ProjectRevision` row가 1개 생성되고 `user_id`가 요청한 사용자와 일치함 |
| T-03 | 리비전 목록/단건 조회 API (Red→Green) | `GET /projects/{project_id}/revisions` — 해당 프로젝트 멤버만 접근 가능(403), `id`/`created_at`/`username` 목록을 최신순으로 반환(content 제외, 목록은 가볍게). `GET /projects/{project_id}/revisions/{revision_id}` — 단건 조회 시 `content` 포함 전체 반환. | 1.5시간 | T-02 | 테스트 4개: 멤버 아니면 403 / 목록이 최신순 / 목록엔 content 없음 / 단건 조회엔 content 있음 |
| T-04 | 전체 테스트 + 정리 | `pytest web-server/tests -v` 전체 통과 확인, `/simplify`로 과설계 없는지 확인. | 30분 | T-03 | 전체 테스트 PASS |

## Day 2 — 프론트엔드 (UI 구현 후 수동 확인)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-05 | 자동저장 제거 + 저장 버튼 추가 | `page.tsx`의 디바운스 `useEffect`(76-86번째 줄) 삭제. `lastSavedContent` ref도 더 이상 필요 없으면 같이 정리. CLAUDE.md 편집 영역 버튼 줄(다운로드/복사하기/push)에 "저장" 버튼을 추가해서 클릭 시 `saveProjectContent` 호출. 저장 성공 시 아래 리비전 목록도 갱신(T-06과 연결). | 1시간 | 없음(백엔드 API는 기존 PUT 재사용) | 타이핑만 해서는 저장 안 되고, "저장" 버튼을 눌러야 서버에 반영됨을 수동 확인 |
| T-06 | `lib/projects.ts`에 리비전 API 함수 추가 | `listRevisions(projectId)`, `getRevision(projectId, revisionId)` 추가. `Revision` 타입(`id`, `created_at`, `username`) 정의. | 30분 | T-03 | `npx tsc --noEmit` 통과 |
| T-07 | aside에 "변경 이력" 박스 추가 | "세션 업로드" 박스 **아래**에 "변경 이력" 박스 추가. 프로젝트 로드 시 + 저장 성공 시 `listRevisions` 호출해서 목록 렌더(시각 + username). 목록 비어있으면 "저장 기록이 없습니다" 같은 빈 상태 문구. | 1시간 | T-05, T-06 | 저장할 때마다 새 항목이 목록 맨 위에 추가되는지 수동 확인 |
| T-08 | 리비전 미리보기 모달 | 목록 항목 클릭 시 기존 초대 모달과 같은 패턴(배경 클릭/취소로 닫힘)으로 모달 열고, `getRevision`으로 받은 content를 읽기 전용(`<pre>` 또는 `disabled` textarea)으로 표시. 복원 버튼은 만들지 않음(범위 밖). | 1시간 | T-06, T-07 | 항목 클릭 → 그 시점 전체 내용이 모달에 뜨는지, 다른 항목 클릭 시 내용이 바뀌는지 수동 확인 |
| T-09 | 검증 + 정리 | `npx tsc --noEmit`, 브라우저에서 로그인 2계정으로 저장→목록 갱신→모달 미리보기 전체 시나리오 수동 확인. `/simplify`로 과설계 없는지 확인. | 30분 | T-08 | 타입 체크 통과 + 수동 시나리오 통과 |

---

## 이번 스프린트에서 다루지 않는 것 (명시적으로 범위 밖)

- 리비전 diff(추가/삭제 줄 수) 표시 — 나중에 필요하면 별도 스프린트
- 리비전으로 "복원"하는 기능 — 지금은 미리보기만
- 리비전 목록 페이지네이션/무한스크롤 — 프로젝트당 저장 횟수가 많지 않을 것으로
  가정, 필요해지면 그때 추가
- 웹소켓으로 다른 사람이 저장했을 때 실시간으로 목록 갱신 — 지금은 내가 저장했을
  때 + 페이지 진입 시에만 갱신
