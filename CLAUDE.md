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

## 4. 이 프로젝트 특화 컨텍스트

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
