# AI 서버 스프린트 (3일)

**스프린트 목표**: AI 기능 정상 작동 및 서버 구축 — `docs/superpowers/plans/2026-07-10-ai-server.md`의
6개 TDD 태스크를 완성하고, `DESIGN.md` 리뷰(2026-07-11)에서 나온 AI서버 관련 TODO를
반영해서 실제로 동작하는 `/analyze`, `/embed` 서버를 만든다.

**참고 문서**: `DESIGN.md`, `CLAUDE.md`(스프린트 워크플로우), `docs/superpowers/plans/2026-07-10-ai-server.md`

**워크플로우 원칙 적용** (`CLAUDE.md` 4절 기준):
- 모호한 설계 결정은 코드 짜기 전에 브레인스토밍으로 먼저 정리 (Day 1 T-01, T-02)
- 태스크마다 Red(실패 테스트)→Green(최소 구현)→Refactor 사이클 준수
- 각 태스크 끝날 때 요구사항/에러 없음 확인 (verification-before-completion)
- 스프린트 마무리에 `/simplify` + `/code-review` + `document-release` 순서
- 문제 생기면 즉흥 패치 대신 재현 테스트부터 (systematic-debugging)

---

## Day 1 — 설계 결정 + 기반 구축

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-01 | 프롬프트 설계 결정 (DESIGN.md 섹션5 TODO) | 코드 짜기 전에 브레인스토밍으로 확정: 한 번의 Gemini 호출에 분류+이유설명+커맨드/문구생성+confidence를 다 시킬지, 나눌지. 옵션별 RPM 영향과 트레이드오프를 표로 정리. "flash-lite가 요구사항 많으면 품질 떨어진다"는 관찰은 이 시점엔 가설로만 남기고, 실측은 T-07에서. | 1시간 | 없음 | 결정 사항과 근거가 `docs/superpowers/plans/2026-07-10-ai-server.md`에 반영됨 (한 호출로 갈지, 나눌지 명시) |
| T-02 | RPM 실측 확인 (DESIGN.md 섹션6 TODO) | 팀 계정 AI Studio 대시보드에서 `gemini-2.5-flash-lite`/`gemini-embedding-001`의 실제 RPM/RPD 한도 확인. | 30분 | 없음 (T-01과 병렬 가능) | 실측 RPM 값을 기록, `aiolimiter` 설정값(현재 추정치 8)을 실측 기반으로 확정 |
| T-03 | 스키마 정의 (Red→Green) | `ai-server/schemas.py`: `HookCandidate`, `ClaudeMdCandidate`, `AnalyzeRequest/Response`, `EmbedRequest/Response`. 실패 테스트 먼저 작성 후 구현. | 2시간 | T-01 | `pytest tests/test_schemas.py -v` 2개 테스트 통과 |
| T-04 | RPM 보호용 rate limiter (분리 반영, DESIGN.md 섹션7 TODO 수정) | `ai-server/rate_limit.py`: 원래 플랜은 `analyze`/`embed`가 limiter 하나를 공유하는 구조였는데, 이건 임베딩이 생성 쿼터를 불필요하게 갉아먹는 버그였음(섹션7 TODO). **생성용/임베딩용 limiter를 분리**해서 구현. 값은 T-02 실측 기반. | 1.5시간 | T-02, T-03 | 두 limiter가 독립적으로 존재하고 각각 테스트 통과, 왜 분리했는지 주석에 명시 |

---

## Day 2 — 핵심 로직 구현

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-05 | Gemini 생성 호출 래퍼 | `ai-server/gemini_client.py`: `call_gemini_analyze`. 타임아웃 15초 + 재시도 1회, 실패 시 `GeminiCallFailed`. T-01 결정대로 시스템 프롬프트 구성, T-04의 생성용 limiter 사용. Red→Green→Refactor. | 3시간 | T-04 | 4개 테스트 통과 (첫시도 성공/재시도 후 성공/2회 실패/malformed 응답) |
| T-06 | Gemini 임베딩 호출 래퍼 | `ai-server/embed_client.py`: `call_gemini_embed`, `gemini-embedding-001`, T-04의 임베딩 전용 limiter 사용. | 2시간 | T-04 | 2개 테스트 통과 |
| T-07 | FastAPI 앱 — `/analyze`, `/embed` | `ai-server/main.py`: 의존성 주입으로 Gemini 클라이언트 교체 가능하게. 실패 시 503 반환. | 2.5시간 | T-05, T-06 | 3개 테스트 통과 (성공/503/embed 성공) |

---

## Day 3 — 검증 + 마무리

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 |
|---|---|---|---|---|---|
| T-08 | 로컬 실행 확인 + 품질 실측 | 전체 테스트 스위트 실행. 실제 Gemini 키로 로컬 서버 기동 후 curl 테스트 — flash-lite의 hook/claude_md 분류 품질, reason 문장 품질을 실제로 확인 (T-01의 가설 검증). 품질 문제 있으면 `flash`로 되돌릴지 이 시점에 판단. | 2시간 | T-07 | 전체 테스트 PASS, 실제 curl 응답에서 candidates 배열 확인, 품질 판단 결과 문서에 기록 |
| T-09 | 코드 리뷰 + 문서화 | `/code-review` (필요시 `--fix`) 돌리고, 통과하면 `document-release`로 관련 문서 갱신. `/simplify`로 과설계 없는지 마지막 확인. | 1.5시간 | T-08 | 리뷰 이슈 없음 또는 전부 반영 완료, 문서 갱신 커밋 |
| T-10 (스트레치) | skill 후보 스키마 사전 준비 | hook/claude_md가 안정화된 뒤이므로, `SkillCandidate` 스키마만 추가(시스템 프롬프트 few-shot 통합은 웹서버 쪽 준비 확인 후 별도 스프린트에서 — DESIGN.md Next Steps 4번 순서 유지). | 1.5시간 | T-09 | 스키마 테스트 통과, 시스템 프롬프트엔 아직 미통합이라는 점이 문서에 명시됨 |

---

## 이 스프린트에서 반드시 결정해야 하는 것 (DESIGN.md TODO 중 AI서버 블로킹 항목)

- **섹션 5**: 한 호출에 몇 개 일을 시킬지 (T-01)
- **섹션 6**: 실제 RPM/RPD 한도 (T-02)
- **섹션 7**: `analyze`/`embed`가 limiter를 공유하던 버그 수정 (T-04)

나머지 TODO(섹션 1, 3의 skill 전처리/임계값/병합기준, 섹션 6의 v2 모니터링 시스템)는
이 스프린트 범위 밖 — 각각 스프린트3, v2 로드맵으로 남겨둠.
