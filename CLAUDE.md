# 개발 가이드라인

TDD(Red-Green-Refactor)와 Karpathy 4원칙(Think Before Coding, Simplicity First,
Surgical Changes, Goal-Driven Execution)을 통합한 이 프로젝트의 개발 워크플로우.

## 1. 기본 워크플로우 (개발 사이클)

모든 기능 구현은 아래 순서를 따른다:

1. **Think Before Coding** — 요구사항이 모호하면 코드/테스트 작성 전에 먼저
   질문하거나 가정을 명시한다.
2. **Red** — 실패하는 테스트를 먼저 작성한다. 이때 테스트는 "성공 기준"을
   구체적이고 검증 가능한 형태로 표현해야 한다 (Goal-Driven Execution).
3. **Green** — 테스트를 통과시키는 최소한의 코드만 작성한다. 요청받지 않은
   기능, 추상화, 유연성은 추가하지 않는다 (Simplicity First).
4. **Refactor** — 테스트가 통과하는 상태를 유지하면서 구조를 정리한다. 이때
   변경 범위는 해당 작업과 직접 관련된 코드로 한정한다 (Surgical Changes).

## 2. 각 원칙의 구체적 규칙

- **Think Before Coding**: 요구사항에 여러 해석이 가능하면 침묵하고 임의로
  고르지 말고, 해석을 명시하거나 사용자에게 물어본다.
- **Simplicity First**: "시니어 엔지니어가 봤을 때 과설계다"라고 판단되면 더
  단순하게 다시 짠다. 미리 확장성을 깔지 않는다(단, 사용자가 명시적으로
  요구한 확장 포인트는 예외).
- **Surgical Changes**: 변경한 모든 줄은 요청과 직접 연결되어야 한다. 이번
  작업과 무관한 코드 스타일/포맷/리팩토링은 건드리지 않는다. 단, 내 변경으로
  인해 생긴 미사용 import/dead code는 정리한다.
- **Goal-Driven Execution**: 막연한 지시("이거 고쳐줘")를 받으면, 검증 가능한
  성공 조건(테스트, assert, 출력 형식 등)으로 변환한 뒤 그 기준을 통과할
  때까지 반복한다.

## 3. 테스트 관련 세부 규칙

- 새 기능/버그 수정 시 반드시 대응하는 테스트를 먼저 작성한다 (unit test
  우선, 필요시 integration test).
- 테스트 없이 프로덕션 코드부터 작성하지 않는다.
- 기존 테스트를 통과시키기 위해 테스트 코드 자체를 조작하지 않는다 (테스트가
  잘못됐다고 판단되면 이유를 설명하고 사용자에게 확인받는다).

## 4. 스프린트 워크플로우 (요구사항 → 구조 → 개발 → 리뷰 → 문서화)

각 단계에서 어떤 스킬을 쓰는지 고정해둔다. **새로운 문서 파일이나 hook 자동화는
만들지 않는다** — git 커밋 메시지, 회귀 테스트, `DESIGN.md`가 이미 기록 역할을
하므로 별도 로그 파일(결정/리뷰/테스트 기록용)은 두지 않기로 결정함(2026-07-11,
Simplicity First 근거).

0. **매일 작업 시작 시**: `docs/sprints/`의 해당 스프린트 문서를 먼저 확인하고,
   그날 분량의 태스크부터 순서대로(의존성 순서 지켜서) 진행한다. 스프린트 문서에
   없는 작업을 임의로 먼저 하지 않는다 — 순서가 바뀌면 의존성이 깨질 수 있음.
1. **요구사항 정의**: 스프린트 시작 전 애매한 부분이 있으면 `superpowers:brainstorming`으로
   짧게 정리 → `superpowers:writing-plans`로 검증 가능한 계획으로 변환. 매 스프린트마다
   격식 차릴 필요는 없고, 애매함이 실제로 있을 때만.
2. **구조 잡기**: 이 문서(`CLAUDE.md`)와 `DESIGN.md`가 그 역할. 별도 `rules/` 디렉토리나
   언어별 규칙 파일로 쪼개지 않는다 — 2인 팀 규모에 과함.
3. **개발**:
   - 태스크마다 `superpowers:subagent-driven-development`로 플랜 파일(`docs/superpowers/plans/*.md`) 실행.
   - 구현은 위 1절의 Red-Green-Refactor 사이클(`superpowers:test-driven-development`)을 따름.
   - 완료 전 `superpowers:verification-before-completion`으로 요구사항 충족/에러 없음 확인.
   - 스프린트 마무리 시 `/simplify`(gstack)로 Simplicity First 위반 없는지 한 번 훑기.
4. **리뷰 → 문서화** (수동 순서 실행, 자동 파이프라인 아님):
   1. `/code-review`(gstack, 필요시 `--comment`로 PR에 남김) 또는 `/codex challenge` —
      `superpowers:requesting-code-review`/`receiving-code-review` 절차로 "요청과 무관한
      변경 없는지" 확인.
   2. 통과하면 `document-release`(gstack)로 README/CHANGELOG 갱신.
5. **브랜치/머지** (2026-07-12 확정): `main`=배포 가능한 안정 브랜치, `develop`=통합
   브랜치. 각자 트랙은 `feature/ai-server`, `feature/web-server`처럼 `feature/*`
   브랜치에서 작업(`superpowers:using-git-worktrees`로 작업공간 분리) → `develop`으로
   merge → 스프린트 끝나면 `develop → main`. **`develop`에 직접 push 금지** — 오늘
   직접 push하다가 두 사람 히스토리가 갈라져서 충돌 처리한 적 있음(2026-07-12),
   재발 방지. 머지는 스프린트 단위로 묶어서(태스크마다 X), `superpowers:finishing-a-development-branch`.
   디렉토리 구조는 `DESIGN.md`의 "디렉토리 구조" 절 참고(여기서 중복 안 함).
6. **보안 게이트**: GitHub API/토큰 관련 코드가 바뀌었거나 `develop → main` 머지 직전엔
   `/security-review` 또는 `/cso`(gstack)를 반드시 돌린다.
7. **버그 발생 시**: 즉흥 패치 대신 `superpowers:systematic-debugging`으로 접근 —
   재현하는 회귀 테스트를 먼저 만들고 고친다 (이게 곧 "테스트 문서" 역할을 겸함).

**이 워크플로우를 정할 때 쓴 판단 기준** (일반화해서 앞으로도 적용): 팀 규모/기간 대비
비용-효과, 반복될 절차인지(반복 안 되면 자동화 가치 낮음), 이미 있는 도구로 커버되는지
(있으면 재발명 안 함), 실패 시 대가가 큰 지점인지(그런 곳만 별도 게이트).

## 5. 이 프로젝트 특화 컨텍스트

- **스택**: FastAPI(웹서버 + AI 서버, 분리 배포) + Gemini API
  (`gemini-2.5-flash-lite` 생성, `gemini-embedding-001` 임베딩) + Next.js
  (App Router, BFF 프록시) — 자세한 아키텍처는 `DESIGN.md` 참고.
- **백엔드 테스트 프레임워크**: `pytest` + `pytest-asyncio`(비동기 엔드포인트/
  Gemini 호출 테스트) + `httpx`(`TestClient`, `MockTransport`로 외부 HTTP
  스텁). Gemini 클라이언트는 의존성 주입으로 가짜 클라이언트를 넣어 목킹한다
  (별도 `pytest-mock` 불필요 — `docs/superpowers/plans/` 하위 플랜의 기존
  테스트 패턴 참고).
- **프론트엔드 테스트 프레임워크**: `vitest` + React Testing Library.
- 이 가이드라인은 프로젝트별 규칙과 병합 가능하며, 충돌 시 프로젝트 규칙이
  우선한다.
