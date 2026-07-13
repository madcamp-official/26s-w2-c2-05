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

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 | 관련 DESIGN.md 섹션 |
|---|---|---|---|---|---|---|
| T-01 | 프롬프트 설계 결정 (DESIGN.md 섹션5 TODO) | 코드 짜기 전에 브레인스토밍으로 확정: 한 번의 Gemini 호출에 분류+이유설명+커맨드/문구생성+confidence를 다 시킬지, 나눌지. 옵션별 RPM 영향과 트레이드오프를 표로 정리. "flash-lite가 요구사항 많으면 품질 떨어진다"는 관찰은 이 시점엔 가설로만 남기고, 실측은 T-07에서. | 1시간 | 없음 | 결정 사항과 근거가 `docs/superpowers/plans/2026-07-10-ai-server.md`에 반영됨 (한 호출로 갈지, 나눌지 명시) | **섹션 5**(프롬프트 설계 원칙) — TODO 4항목 전체(호출 분리 개수/RPM영향/트레이드오프 정리) 해결 대상. 마지막 항목("flash-lite 품질 저하 실측")은 이 태스크가 아니라 T-08에서 해결 |
| T-02 | RPM 실측 확인 (DESIGN.md 섹션6 TODO) — **완료 (2026-07-13)** | 팀 계정 AI Studio 대시보드에서 확인 완료: `gemini-2.5-flash-lite` RPM 10/TPM 250K/**RPD 20**, `gemini-embedding-001` RPM 100/TPM 30K/RPD 1,000. RPD 20이 예상보다 낮아 T-04 스코프에 일일 사전 차단 로직이 추가됨(아래 T-04 참고). | 30분 | 없음 (T-01과 병렬 가능) | 실측 RPM/RPD 값 기록 완료, `aiolimiter` 설정값을 RPM 10 기반으로 확정 | **섹션 6**(Gemini 모델/무료 티어 제약) — TODO 1번째 항목 해결(`DESIGN.md`에 실측값 반영 완료). 같은 섹션의 v2 모니터링 시스템 TODO는 범위 밖 |
| T-03 | 스키마 정의 (Red→Green) | `ai_server/schemas.py`: `HookCandidate`, `ClaudeMdCandidate`, `AnalyzeRequest/Response`, `AnalyzeEndpointResponse`(candidates+remaining_rpd, 2026-07-13 결정), `EmbedRequest/Response`. 실패 테스트 먼저 작성 후 구현. | 2시간 | T-01 | `pytest tests/test_schemas.py -v` 3개 테스트 통과 | 대응하는 TODO 항목 없음. **섹션 1**(추천 타입 3종)의 `HookCandidate`/`ClaudeMdCandidate` 정의를 hook·claude_md 두 타입만 구현(skill 제외, T-10에서 별도). "API 엔드포인트"/"2인 팀 병렬 작업 전략" 절의 AI서버-웹서버 스키마 계약을 확정 |
| T-04 | RPM 보호용 rate limiter + 일일 RPD 사전 차단 (분리 반영 + 스코프 확장, DESIGN.md 섹션7 TODO 수정, 2026-07-13 결정) | `ai_server/rate_limit.py`: **생성용/임베딩용 limiter를 분리**해서 구현(섹션7 TODO 해결, 값은 T-02 실측 기반 RPM 10/100). **추가로 생성용 일일 RPD 카운터**(자정 리셋, 20 도달 시 Gemini 호출 없이 429 반환)를 구현 — T-02에서 RPD 20이 실질적 병목으로 확인돼 스코프에 추가됨. `/analyze` 응답에 잔여 RPD 필드 노출(웹서버→프론트 전달용). | 2시간 (기존 1.5시간 + RPD 카운터 0.5시간) | T-02, T-03 | 두 RPM limiter가 독립적으로 존재하고 각각 테스트 통과, RPD 카운터가 20에서 429를 반환하는 테스트 통과, 왜 분리/추가했는지 주석에 명시 | **섹션 7**(처리 방식 확정) — TODO 1번째 항목(limiter 공유 버그) 해결 + 2026-07-13 신규 결정(RPD 사전 차단, 429/503 구분) 반영. 같은 섹션 2번째 TODO(claude_md 임베딩 순차 호출 병렬화)는 범위 밖 |

---

## Day 2 — 핵심 로직 구현

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 | 관련 DESIGN.md 섹션 |
|---|---|---|---|---|---|---|
| T-05 | Gemini 생성 호출 래퍼 | `ai_server/gemini_client.py`: `call_gemini_analyze`. 타임아웃 15초 + 재시도 1회, 실패 시 `GeminiCallFailed`. T-01 결정대로 시스템 프롬프트 구성, T-04의 생성용 limiter 사용. Red→Green→Refactor. | 3시간 | T-04 | 4개 테스트 통과 (첫시도 성공/재시도 후 성공/2회 실패/malformed 응답) | 대응하는 TODO 항목 없음. **섹션 5**(T-01 결정 반영), "처리 방식 확정" 절의 타임아웃 15초/재시도 1회 확정 사항 구현, Resolved Questions의 "Gemini 호출 실패 시 유저 경험"(재시도 1회 후 실패 메시지) 결정 구현 |
| T-06 | Gemini 임베딩 호출 래퍼 | `ai_server/embed_client.py`: `call_gemini_embed`, `gemini-embedding-001`, T-04의 임베딩 전용 limiter 사용. | 2시간 | T-04 | 2개 테스트 통과 | 대응하는 TODO 항목 없음(섹션7 TODO는 T-04에서 이미 해결). **섹션 7**(처리 방식 확정) — T-04가 분리한 임베딩 전용 limiter를 소비. **섹션 4**(병합 로직)에서 쓰일 임베딩이지만 매칭 로직 자체는 이 스프린트 범위 밖 |
| T-07 | FastAPI 앱 — `/analyze`, `/embed` | `ai_server/main.py`: 의존성 주입으로 Gemini 클라이언트 교체 가능하게. **할당량 소진(RPD 카운터 0 또는 Gemini 실제 429) 시 429, 그 외 실패(타임아웃/malformed 등 `GeminiCallFailed`) 시 503 반환**(2026-07-13 결정) — `/analyze` 응답에 잔여 RPD 필드 포함. | 2.5시간 | T-05, T-06 | 5개 테스트 통과 (성공+remaining_rpd/429(RPD 카운터 소진)/429(Gemini 실제 429)/503(그 외 실패)/embed 성공) | "API 엔드포인트" 절의 AI서버 계약 구현 + 2026-07-13 결정(429/503 구분, 잔여 RPD 노출) 반영. **섹션 12** TODO("`sessions.status`의 'failed' 값을 설정하는 코드 없음")와 맞닿아 있지만, 그 TODO 자체는 `web-server`의 예외 처리 몫이라 이 태스크로는 미해결 — AI서버는 429/503 반환까지만 담당 |

---

## Day 3 — 검증 + 마무리

| 태스크 ID | 태스크명 | 상세 내용 | 예상 소요 시간 | 의존성 | 수락 기준 | 관련 DESIGN.md 섹션 |
|---|---|---|---|---|---|---|
| T-08 | 로컬 실행 확인 + 품질 실측 — **실제 API 검증 중 버그 3건 발견·수정 (2026-07-13)** | 전체 테스트 스위트 실행(24/24 PASS). 실제 Gemini 키로 로컬 서버 기동 후 curl 테스트 중 `systematic-debugging`으로 근본 원인 규명: ① `gemini-2.5-flash-lite`가 신규 유저에게 폐기(404) → `gemini-3.1-flash-lite`로 교체(RPM 15/RPD 500, `rate_limit.py` 값도 갱신) ② Gemini `response_schema`가 기본값 있는 필드를 거부 → `type` 필드 기본값 제거 ③ `Union`(`anyOf`)·단일값 `Literal`(`const`) 미지원 → `GeminiAnalyzeSchema`(hook/claude_md 별도 리스트, `type` 없음)로 Gemini 요청 스키마 분리, 응답 변환 로직(`_to_analyze_response`) 추가. 3개 버그 모두 회귀 테스트 작성 후 수정(TDD). | 2시간 | T-07 | 전체 테스트 PASS, 실제 curl 응답에서 candidates 배열 확인, 품질 판단 결과 문서에 기록 | **섹션 5** TODO 마지막 항목("flash-lite는 요구사항이 많을수록 품질이 떨어진다"는 관찰의 실측 검증) — 모델이 3.1로 바뀌어 이 항목 자체는 재검증 필요. **섹션 6**의 모델 리스크 노트 판단 수행. 이 과정에서 발견된 버그들은 `DESIGN.md` "Gemini 모델/무료 티어 제약"·"처리 방식 확정" 절에 반영 완료 |
| T-09 | 코드 리뷰 + 문서화 | `/code-review` (필요시 `--fix`) 돌리고, 통과하면 `document-release`로 관련 문서 갱신. `/simplify`로 과설계 없는지 마지막 확인. | 1.5시간 | T-08 | 리뷰 이슈 없음 또는 전부 반영 완료, 문서 갱신 커밋 | 대응하는 TODO 항목 없음. DESIGN.md "리뷰 상태" 절 갱신 대상 |
| T-10 (스트레치) | skill 후보 스키마 사전 준비 | hook/claude_md가 안정화된 뒤이므로, `SkillCandidate` 스키마만 추가(시스템 프롬프트 few-shot 통합은 웹서버 쪽 준비 확인 후 별도 스프린트에서 — DESIGN.md Next Steps 4번 순서 유지). | 1.5시간 | T-09 | 스키마 테스트 통과, 시스템 프롬프트엔 아직 미통합이라는 점이 문서에 명시됨 | **섹션 1**(추천 타입 3종) 일부만 해결 — 스키마 추가뿐이며, TODO의 "전처리 요구사항/방법 미정"·"최소 반복 임계값 미정"·"팀 모드 병합 기준 미정" 3항목은 미해결 상태 유지(스코프 밖). Next Steps 4번 항목("hook/claude_md 안정화 후 skill 얹기") 순서 준수. **섹션 3** TODO(다단계 시퀀스 추출 로직)도 이 태스크로는 미해결 |

---

## 이 스프린트에서 반드시 결정해야 하는 것 (DESIGN.md TODO 중 AI서버 블로킹 항목)

- **섹션 5**: 한 호출에 몇 개 일을 시킬지 (T-01)
- **섹션 6**: 실제 RPM/RPD 한도 (T-02)
- **섹션 7**: `analyze`/`embed`가 limiter를 공유하던 버그 수정 (T-04)

나머지 TODO(섹션 1, 3의 skill 전처리/임계값/병합기준, 섹션 6의 v2 모니터링 시스템)는
이 스프린트 범위 밖 — 각각 스프린트3, v2 로드맵으로 남겨둠.
