# 초대 + 실시간 접속 표시 스프린트 (1일)

**스프린트 목표**: (1) 프로젝트 owner가 `user_id`로 다른 사용자를 프로젝트에 초대할 수 있게
하고, (2) 프로젝트 편집 화면 오른쪽 위에 현재 그 프로젝트에 접속 중인 사용자를 실시간으로
보여준다(WebSocket 기반).

**참고 문서**: `CLAUDE.md`(스프린트 워크플로우), `web-server/models.py`(`ProjectMember`),
`web-server/routers/projects.py`, `web-server/deps.py`(`get_current_user`)

**워크플로우 원칙 적용** (`CLAUDE.md` 4절 기준):
- 설계 결정(초대 방식, WS 인증 방식)은 코드 짜기 전에 T-01에서 먼저 확정
- 태스크마다 Red(실패 테스트)→Green(최소 구현)→Refactor 사이클 준수
- 각 태스크 끝날 때 요구사항/에러 없음 확인 (verification-before-completion)
- GitHub 토큰과 무관한 스프린트이므로 이번엔 `/security-review` 필수 게이트 대상 아님
  (단, 인증 토큰을 WS 쿼리 파라미터로 노출하는 부분은 T-01에서 리스크 명시)

---

## Day 1 (오늘)

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-01 | 설계 결정 확정 | ① **초대 방식**: 별도 초대/수락 테이블 없이, owner가 `user_id`를 지정하면 즉시 `ProjectMember(role="member")`로 추가되는 방식으로 확정 (수락 플로우는 이번 스프린트 범위 밖, Simplicity First). ② **WS 인증**: 브라우저 WebSocket은 커스텀 `Authorization` 헤더를 못 보내므로, 기존 JWT를 쿼리 파라미터(`?token=`)로 전달해 `decode_access_token`으로 검증하는 방식으로 확정. 토큰이 URL/로그에 남을 수 있다는 점은 알려진 트레이드오프로 문서에 기록만 하고 이번 스프린트에서는 완화책(단기 티켓 발급 등) 도입하지 않음. | 30분 | 없음 | 두 결정과 근거가 이 문서에 반영됨(반영 완료) |
| T-02 | 초대 API (Red→Green) | `web-server/routers/projects.py`: `POST /projects/{project_id}/invite`, body `{user_id: int}`. owner만 호출 가능(아니면 403), 대상 `user_id`가 존재하지 않으면 404, 이미 멤버면 400, 성공 시 `ProjectMember(role="member")` 생성. | 1.5시간 | T-01 | 테스트 4개 통과: owner 아님→403 / 대상 유저 없음→404 / 이미 멤버→400 / 성공 시 멤버 추가 확인 |
| T-03 | 초대 프론트 UI | `frontend/app/project/[id]/page.tsx`: owner에게만 보이는 "user_id로 초대" 입력창 + 버튼 추가. `frontend/lib/projects.ts`에 `inviteMember(projectId, userId)` 함수 추가. | 1시간 | T-02 | vitest로 "owner에게만 보임 / 성공 시 안내 메시지 / 실패 시 에러 메시지" 확인 |
| T-04 | WebSocket 접속 현황 엔드포인트 (Red→Green) | `web-server/routers/projects.py`(또는 신규 `ws.py`)에 `WS /ws/projects/{project_id}?token=`. 연결 시 토큰 검증 + 해당 프로젝트 `ProjectMember` 여부 확인(아니면 close). 프로젝트별 in-memory `ConnectionManager`(`dict[project_id, set[(user_id, websocket)]]`)로 연결 관리. 연결/해제 시마다 현재 접속자 목록(`user_id`, `username`)을 그 프로젝트의 모든 연결에 broadcast. | 2.5시간 | T-01 | pytest `TestClient.websocket_connect`로: 멤버 아니면 연결 거부 / 2명 연결 시 서로에게 갱신된 목록이 broadcast됨 / 1명 해제 시 남은 연결에 갱신된 목록이 옴 |
| T-05 | 프론트 — 접속 중 표시 | 프로젝트 페이지 진입 시 `/ws/projects/{id}?token=`으로 연결, 받은 접속자 목록을 헤더 오른쪽 위에 아바타/이름 뱃지로 렌더. 페이지 이탈 시 연결 정리(`useEffect` cleanup). | 1.5시간 | T-04 | 브라우저 탭 2개로 같은 프로젝트 열었을 때 서로가 "접속 중" 목록에 보이고, 탭 하나 닫으면 목록에서 사라짐(수동 확인) |
| T-06 | 검증 + 마무리 | 전체 테스트(`pytest`, `vitest`) 실행. 로컬에서 웹서버+프론트 기동 후 두 브라우저 탭으로 초대→동시 접속 시나리오 수동 확인. `/simplify`로 과설계 없는지 확인. | 1시간 | T-02~T-05 | 전체 테스트 PASS, 수동 시나리오(초대 후 상대 계정으로 프로젝트 접근 가능 + 동시 접속 표시) 통과 |

---

## 이번 스프린트에서 다루지 않는 것 (명시적으로 범위 밖)

- 초대 수락/거절 플로우, 초대 알림 — owner가 넣으면 즉시 멤버 (T-01 결정)
- WS 재연결/heartbeat, 다중 서버 프로세스 간 접속자 상태 공유(Redis pub/sub 등) — 지금은 단일 프로세스 in-memory로 충분 (스케일 나오면 별도 스프린트)
- 멤버 강퇴/역할 변경 UI — 이번 스프린트는 "초대"까지만
