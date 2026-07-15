# 26s-w2-c2-05

## 공통과제 II : 협업형 실전 산출물 제작 (2인 1팀)

**목적:** 실시간 인터랙션, LLM Wrapper, Cross-Platform 중 하나의 옵션을 선택해 구현하며, 선택한 기술을 실제로 동작하는 형태의 산출물로 완성한다.

**선택 옵션:**

| 옵션 | 설명 |
|---|---|
| 실시간 인터랙션 | 사용자 간 상태 변화, 실시간 데이터 흐름, 스트리밍 응답 등 실시간성이 드러나는 기능을 구현 |
| LLM Wrapper | LLM API를 활용하여 AI 기능이 포함된 산출물을 구현 |
| Cross-Platform | 하나의 산출물을 여러 실행 환경에서 사용할 수 있도록 구현* |

> *데스크톱 앱 ↔ 모바일 앱; 혹은 다른 폼팩터에서의 앱; 웹만/웹 기반 프레임워크(Electron, Tauri 등) 대신 다른 프레임워크를 시도해보는 것을 적극 권장

**결과물:** 선택한 옵션이 적용된 작동 가능한 산출물, 실행 가능한 코드, 시연 자료 및 관련 문서

---

## 팀원

| 이름 | 학교 | GitHub | 역할 |
|---|---|---|---|
| 박서윤 | 이화여자대학교 | banunas | AI서버 담당 |
| 최재윤 | KAIST | Jaeyun-18 | 웹 서버 및 배포 담당 |

---

## 선택 옵션

- [x] 실시간 인터랙션
- [x] LLM Wrapper
- [ ] Cross-Platform

---

## 기획안

- **산출물 주제:** Claude Code 세션 로그 → 팀 개발 환경(hook / CLAUDE.md / Skill) 추천 툴
- **제작 목적:** Claude Code 같은 Agent AI는 쓰지만 hook·CLAUDE.md·skill 같은 개발 환경
  구축은 못 하는 주니어/취미 개발자를 위해, 세션 로그만 올리면 그 사람(또는 팀)에게
  맞춘 개발 환경 설정을 Gemini가 자동으로 뽑아준다. 개인용 세션 분석기는 이미 있지만,
  여러 명의 세션을 모아 "이 팀은 이렇게 일한다"는 팀 공통 컨벤션을 자동으로 도출해주는
  도구는 없다는 게 차별화 지점.
- **선택 옵션:** LLM Wrapper — Gemini API(`gemini-3.1-flash-lite` 생성,
  `gemini-embedding-001` 임베딩)로 세션 로그를 분석해 추천을 생성.
- **핵심 구현 요소:**
  - 세션 로그(JSONL) 업로드 → Gemini 구조화 생성 호출로 hook / CLAUDE.md / Skill
    후보 추출 (개인 모드)
  - 팀원별 후보를 기존 그룹과 점진적으로 매칭(hook은 문자열 정규화, claude_md/skill은
    임베딩 코사인 유사도) → 2명 이상 겹치면 팀 공통 추천으로 자동 승격
  - GitHub OAuth 연동 — 승격된 추천을 유저 승인 후 실제 레포에 반영(push)
  - WebSocket 기반 실시간 접속자 표시 및 동시 편집 충돌 방지
- **사용 / 시연 시나리오:** 팀장이 프로젝트 생성 → 공유 코드로 팀원 초대 → 각자
  Claude Code 세션 JSONL 업로드 → 업로드한 사람은 자신만의 개인 추천을 바로 확인 →
  2명 이상에게서 겹치는 패턴이 나오면 팀 공통 추천으로 자동 승격되고 근거(몇 명 중
  몇 명에게서 나왔는지)가 함께 표시됨 → GitHub 연동 후 승인하면 팀 레포에 반영.
- **팀원별 역할:** 서버를 웹서버(FastAPI + SQLite + Next.js, 인증·GitHub 연동·
  비즈니스 로직)와 AI 서버(FastAPI, Gemini 생성/임베딩 전담, DB 없는 순수 함수형
  서비스)로 분리해 두 사람이 독립적으로 병렬 개발할 수 있게 구성.

### 개발 일정

| 날짜 | 목표 |
|---|---|
| Day 1 (07-09) | 저장소 초기화, 과제 요구사항 정리 |
| Day 2 (07-10) | 브레인스토밍 → `DESIGN.md` 작성, 추천 타입(hook/CLAUDE.md) 스키마와 아키텍처/기술스택 확정 |
| Day 3 (07-11) | 개발 워크플로우(`CLAUDE.md`) 확립, 웹서버 기본 구조·회원가입·프로젝트 생성·GitHub 연동 착수 |
| Day 4 (07-12) | 설계 문서 정리, 스프린트 태스크(`docs/sprints/`) 분해 |
| Day 5 (07-13) | AI 서버 구현 완료(`/analyze`, `/embed`, RPM/RPD 제한), 웹서버-AI서버 연동, 실시간 접속 확인(WS) |
| Day 6 (07-14) | 세 번째 추천 타입(Skill) 추가, 온보딩 기능, 동시 편집 충돌 처리, 배포 준비 |
| Day 7 (07-15) | 배포 마무리, 문서 정리 |

---

## 구현 명세서

| 구현 요소 | 설명 | 우선순위 |
|---|---|---|
| 세션 로그 업로드 → 개인 추천 | JSONL 업로드 → 규칙 기반 전처리 → Gemini 구조화 생성 호출 → hook/CLAUDE.md/Skill 후보 반환 | 필수 |
| 팀 공통 추천 자동 승격 | 후보를 기존 그룹과 매칭(문자열 정규화 또는 임베딩 유사도) → 2명 이상 겹치면 근거와 함께 자동 승격 | 필수 |
| 회원가입/로그인 | JWT 기반 인증, 프로젝트 멤버십 관리 | 필수 |
| Gemini 사용량(RPD) 보호 | `aiolimiter` 기반 RPM 보호 + 일일 RPD 사전 차단(429), 잔여 쿼터를 프론트에 노출 | 필수 |
| GitHub OAuth 연동 및 반영 | GitHub 로그인 연동 후 승인 시 병합 결과를 레포에 push | 선택 |
| 실시간 접속자 표시 | WebSocket으로 프로젝트 내 접속 중인 팀원 목록 및 편집 충돌 방지 브로드캐스트 | 선택 |
| 신규 프로젝트 온보딩 | 기존 코드베이스 기반 초기 CLAUDE.md 자동 생성 | 선택 |

---

## 아키텍처

```
                          Internet (심사위원 등)
                                 │
                    Cloudflare Tunnel — 라우트 1개만
                                 │
                                 ▼
                     [Next.js 서버 :3000]  ← 유일하게 외부 노출됨
                     (화면 서빙 + next.config.js
                      rewrites()로 /api/* 를 백엔드로
                      통째로 프록시)
                                 │  localhost 내부 호출
                                 ▼
                     [FastAPI 웹 서버 :8000]
                     (SQLite, 인증, 프로젝트/세션/Skill CRUD,
                      GitHub OAuth, WebSocket 실시간 접속)
                                 │  localhost 내부 호출만        │  아웃바운드
                                 ▼                          ▼ (GitHub API)
                     [FastAPI AI 서버 :8001]
                     (Gemini 생성/임베딩, aiolimiter + RPD 카운터)
                     터널 노출 없음 — 외부에서 절대 접근 불가
```

DB(SQLite)가 붙은 웹 서버와 Gemini 쿼터를 쓰는 AI 서버를 인터넷에 직접 노출하지
않고, Next.js 하나만 외부에 노출하는 BFF(Backend-for-Frontend) 구조. 진입점이
하나라 어뷰징 방지(무료 티어 Gemini 쿼터 보호 포함)를 한 곳에서만 신경 쓰면 되고,
브라우저가 항상 같은 origin에만 요청하므로 CORS 설정도 단순해진다.

---

## 설계 문서

> 프로젝트 성격에 따라 필요한 항목만 작성

### 화면 / 인터페이스 설계

Next.js App Router 기준 화면 구성:

| 경로 | 화면 |
|---|---|
| `/` | 랜딩/프로젝트 목록 |
| `/login`, `/signup` | 로그인 / 회원가입 |
| `/project/[id]` | 프로젝트 상세 — CLAUDE.md/hooks/Skill 편집, 세션 업로드, 팀 추천 확인, 실시간 접속자 표시 |
| `/project/[id]/onboarding` | 신규 프로젝트 온보딩(기존 코드베이스 기반 초기 CLAUDE.md 생성) |
| `/fund` | (부가) 펀딩/소개 페이지 |

### 데이터 구조

웹 서버는 SQLite(SQLModel/SQLAlchemy) 파일 하나로 저장한다. 핵심 테이블:

| 테이블 | 역할 |
|---|---|
| `users` | 계정(아이디/비밀번호), GitHub 연동 토큰(암호화 저장) |
| `projects` | 프로젝트별 병합된 `CLAUDE.md`(`content`) / `hooks` 설정(`hooks_content`) 원문 |
| `project_members` | 프로젝트-유저 멤버십 (role 포함) |
| `sessions` | 업로드된 세션 로그의 처리 상태(`processed`/`no_patterns`/`failed`) |
| `personal_recommendations` | 개인 모드 추천 (hook/claude_md), 팀 그룹에 합류 시 `group_id` 연결 |
| `recommendation_groups` | 팀 모드 병합 그룹 — 대표 텍스트/임베딩 벡터, `promoted`(2명 이상 승격 여부) |
| `group_memberships` | 그룹에 합류한 멤버별 원문/근거(reason)/confidence |
| `skills` | 세 번째 추천 타입(Skill) — 이름/설명/절차(`steps_content`) |
| `project_revisions` | CLAUDE.md/hooks/Skill 변경 이력 |
| `github_oauth_states` | GitHub OAuth CSRF `state` 저장 |

AI 서버는 자체 DB를 갖지 않는 순수 함수형 서비스 — Gemini 응답을 그대로
웹 서버에 반환하고, RPM/RPD 카운터만 프로세스 메모리에 유지한다.

### API / 외부 서비스 연동

**웹 서버 (`:8000`)**

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/signup`, `/login` | 회원가입/로그인, JWT 발급 |
| POST | `/projects` | 프로젝트 생성 |
| GET | `/projects`, `/projects/{project_id}` | 내 프로젝트 목록/상세 조회 |
| PUT | `/projects/{project_id}`, `/projects/{project_id}/name`, `/projects/{project_id}/hooks` | CLAUDE.md/이름/hooks 내용 수정 |
| POST | `/projects/{project_id}/onboarding` | 기존 코드베이스 기반 초기 CLAUDE.md 생성 |
| GET | `/projects/{project_id}/revisions` | 변경 이력 조회 |
| POST | `/projects/{project_id}/invite` | 팀원 초대 |
| DELETE | `/projects/{project_id}` | 프로젝트 삭제 |
| POST | `/projects/{project_id}/sessions` | 세션 로그(JSONL) 업로드 → 개인 추천 + 갱신된 팀 그룹 반환 |
| POST | `/projects/{project_id}/recommendation-groups/{group_id}/apply` | 팀 추천 그룹 적용 |
| POST | `/projects/{project_id}/personal-recommendations/{id}/apply` | 개인 추천 적용 |
| GET/PUT/DELETE | `/projects/{project_id}/skills`, `/skills/{skill_id}` | Skill CRUD |
| PUT | `/projects/{project_id}/github` | 반영 대상 GitHub 레포 지정 |
| POST | `/projects/{project_id}/push` | 승인 시 병합 결과를 GitHub 레포에 반영 |
| GET | `/auth/github/login`, `/auth/github/callback`, `/auth/github/status` | GitHub OAuth 연동 |
| POST | `/auth/github/disconnect` | GitHub 연동 해제 |
| GET | `/quota` | 서비스 전체 잔여 Gemini RPD 조회 |
| WS | `/ws/projects/{project_id}` | 실시간 접속자 목록 + 콘텐츠/Skill 변경 브로드캐스트 |

**AI 서버 (`:8001`, 웹 서버에서만 호출, 외부 비노출)**

| Method | Endpoint | 설명 |
|---|---|---|
| POST | `/analyze` | 전처리된 세션 패턴 → Gemini 구조화 생성 → hook/CLAUDE.md/Skill 후보 반환 |
| POST | `/embed` | 텍스트 → Gemini 임베딩 벡터 (팀 모드 유사도 매칭용) |
| POST | `/generate-base-claude-md` | 신규 프로젝트 온보딩용 초기 CLAUDE.md 생성 |
| GET | `/remaining-rpd` | 잔여 일일 생성 요청 한도 조회 |

**외부 서비스**

| 서비스 | 용도 |
|---|---|
| Gemini API (`gemini-3.1-flash-lite`) | 세션 패턴 → hook/CLAUDE.md/Skill 후보 구조화 생성 |
| Gemini API (`gemini-embedding-001`) | 팀 모드 후보 유사도 매칭용 임베딩 |
| GitHub OAuth App | 로그인 연동 + 승인된 추천을 레포에 push |

---

## 산출물 및 실행 방법

- **산출물 설명:** Claude Code 세션 로그(JSONL)를 업로드하면 Gemini가 hook /
  CLAUDE.md / Skill 후보를 추천해주고, 팀원 2명 이상에게서 같은 패턴이 나오면
  팀 공통 컨벤션으로 자동 승격되며, 승인 시 GitHub 레포에 직접 반영까지 되는
  웹 서비스.
- **실행 환경:** Next.js(프론트) + FastAPI 웹 서버(SQLite) + FastAPI AI 서버
  (Gemini 연동) 3개 프로세스, 로컬 또는 KAIST VM(Cloudflare Tunnel) 배포 모두 지원.
- **실행 방법:** 아래 "실행 방법" 참고 — 서비스 3개를 각각 별도 터미널에서 띄운다.
- **시연 영상 / 이미지:** (선택)

### 실행 방법

서비스 3개(`ai-server`, `web-server`, `frontend`)를 각각 별도 터미널에서 띄운다.
`web-server`는 `ai-server` 없이도 뜨지만, 실제 분석 기능은 `ai-server`가 8001번
포트에 떠 있어야 동작한다. `frontend`는 `web-server`(8000)로 `/api/*`를 프록시하므로
`web-server`가 먼저 떠 있어야 한다.

```bash
# 1. AI 서버 (:8001)
cd ai_server
cp .env.example .env        # GEMINI_API_KEY 채우기
pip install -r requirements.txt
cd ..
python3 -m uvicorn ai_server.main:app --reload --port 8001   # 반드시 repo 루트에서 실행 (상대 import 때문)
```

```bash
# 2. 웹 서버 (:8000)
cd web-server
cp .env.example .env        # GITHUB_CLIENT_ID/SECRET, JWT_SECRET, ENCRYPTION_KEY 채우기
pip install -r requirements.txt
cd ..                       # main.py가 상대 임포트를 쓰므로 반드시 저장소 루트에서 실행
uvicorn web-server.main:app --reload --port 8000
```

```bash
# 3. 프론트엔드 (:3000)
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:3000` 접속.

### 기술 구성

| 분류 | 사용 기술 |
|---|---|
| 핵심 기술 | FastAPI(웹 서버 + AI 서버 분리 배포), Next.js 16(App Router), TypeScript, Tailwind CSS |
| 생성/임베딩 LLM | `google-genai` SDK — 생성 `gemini-3.1-flash-lite`, 임베딩 `gemini-embedding-001`, `aiolimiter`로 RPM 보호 + 로컬 RPD 카운터 |
| 실행 환경 | Python 3(FastAPI, uvicorn), Node.js(Next.js), KAIST VM + Cloudflare Tunnel 배포 |
| 데이터 저장 | SQLite(SQLModel/SQLAlchemy) — 웹 서버 전용, AI 서버는 무상태 |
| 인증/보안 | JWT(`pyjwt`), 비밀번호 해싱(`bcrypt`), GitHub 토큰 암호화 저장(`cryptography`) |
| 외부 API / 서비스 | Gemini API, GitHub OAuth App / REST API |
| 실시간 | FastAPI WebSocket (접속자 표시, 편집 충돌 방지) |

---

## 회고 문서

> [KPT 방법론 참고](https://velog.io/@habwa/%EB%8B%A8%EA%B8%B0-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8-%ED%9A%8C%EA%B3%A0-KPT-%EB%B0%A9%EB%B2%95%EB%A1%A0)

### Keep — 잘 된 점, 다음에도 유지할 것

-
-
-

### Problem — 아쉬웠던 점, 개선이 필요한 것

-
-
-

### Try — 다음번에 시도해볼 것

-
-
-

### 팀원별 소감

**박서윤:**

> 

**최재윤:**

> 

---

## 참고 자료

### 실시간 인터랙션

**WebSocket**
- https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API
- https://techblog.woowahan.com/5268/
- https://tech.kakao.com/posts/391
- https://daleseo.com/websocket/
- https://kakaoentertainment-tech.tistory.com/110

**Socket.IO**
- https://socket.io/docs/v4/
- https://inpa.tistory.com/entry/SOCKET-%F0%9F%93%9A-Namespace-Room-%EA%B8%B0%EB%8A%A5
- https://adjh54.tistory.com/549
- https://fred16157.github.io/node.js/nodejs-socketio-communication-room-and-namespace/

**SSE (Server-Sent Events)**
- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- https://developer.mozilla.org/ko/docs/Web/API/Server-sent_events/Using_server-sent_events
- https://api7.ai/ko/blog/what-is-sse

**TCP / UDP Socket**
- https://docs.python.org/3/library/socket.html
- https://inpa.tistory.com/entry/NW-%F0%9F%8C%90-%EC%95%84%EC%A7%81%EB%8F%84-%EB%AA%A8%ED%98%B8%ED%95%9C-TCP-UDP-%EA%B0%9C%EB%85%90-%E2%9D%93-%EC%89%BD%EA%B2%8C-%EC%9D%B4%ED%95%B4%ED%95%98%EC%9E%90

**gRPC Streaming**
- https://grpc.io/docs/what-is-grpc/core-concepts/
- https://tech.ktcloud.com/entry/gRPC%EC%9D%98-%EB%82%B4%EB%B6%80-%EA%B5%AC%EC%A1%B0-%ED%8C%8C%ED%97%A4%EC%B9%98%EA%B8%B0-HTTP2-Protobuf-%EA%B7%B8%EB%A6%AC%EA%B3%A0-%EC%8A%A4%ED%8A%B8%EB%A6%AC%EB%B0%8D
- https://tech.ktcloud.com/entry/gRPC%EC%9D%98-%EB%82%B4%EB%B6%80-%EA%B5%AC%EC%A1%B0-%ED%8C%8C%ED%97%A4%EC%B9%98%EA%B8%B02-Channel-Stub
- https://inspirit941.tistory.com/371
- https://devocean.sk.com/blog/techBoardDetail.do?ID=167433

**WebRTC**
- https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- https://webrtc.org/getting-started/overview
- https://web.dev/articles/webrtc-basics?hl=ko
- https://devocean.sk.com/blog/techBoardDetail.do?ID=164885
- https://beomkey-nkb.github.io/%EA%B0%9C%EB%85%90%EC%A0%95%EB%A6%AC/webRTC%EC%A0%95%EB%A6%AC/
- https://gh402.tistory.com/45
- https://on.com2us.com/tech/webrtc-coturn-turn-stun-server-setup-guide/

**QUIC / WebTransport**
- https://developer.mozilla.org/en-US/docs/Web/API/WebTransport_API
- https://datatracker.ietf.org/doc/html/rfc9000
- https://news.hada.io/topic?id=13888

#### KCLOUD VM / Cloudflare Tunnel 환경별 주의사항

| 환경 | 사용 가능(권장) 기술 | 포트/조건 | 주의할 기술 |
|---|---|---|---|
| **로컬 / 일반 VM** | HTTP/REST, WebSocket, Socket.IO, SSE, TCP Socket, gRPC Streaming, WebRTC, QUIC/WebTransport 등 대부분 가능 | 직접 포트 개방 가능. 예: 3000, 5000, 8000, 8080, 9000 등. 외부 공개 시 방화벽/보안그룹/공인 IP 설정 필요 | WebRTC는 STUN/TURN 필요 가능. QUIC/WebTransport는 HTTP/3 · UDP 지원 필요 |
| **KCLOUD VM (VPN 내부)** | HTTP/REST, WebSocket, Socket.IO, SSE, WebRTC 시그널링 | 접속 기기 VPN 필요. 기본 허용 포트: **22, 80, 443**. 개발 포트(3000, 8000, 8080 등)는 직접 접근 제한 가능 | TCP Socket은 포트 제한 있음. gRPC는 HTTP/2 설정 필요. WebRTC 미디어·UDP·QUIC/WebTransport 비권장 |
| **KCLOUD VM + Tunnel** | HTTP/REST, WebSocket, Socket.IO, SSE, WebRTC 시그널링 | VM의 `localhost:<port>`를 도메인에 연결. `localPort`는 **1024~65535**. 예: 3000, 8000, 8080 가능 | 순수 TCP Socket, UDP, WebRTC 미디어/DataChannel, QUIC/WebTransport 불가. gRPC 보장 어려움 |
| **외부 서비스 + 우리 도메인** | HTTP/REST, WebSocket, Socket.IO, SSE, WebRTC 시그널링 | Vercel/Netlify/Railway/Render/AWS/GCP 등에 배포 후 CNAME/A 레코드 연결. 보통 외부는 **443** 사용 | WebSocket/gRPC/TCP/UDP는 플랫폼 지원 여부 확인 필요. 서버리스 플랫폼은 장시간 연결 제한 가능 |
| **서버 없이 외부 SaaS 사용** | Supabase Realtime, Firebase, Pusher/Ably, LLM API Streaming | 직접 포트 관리 불필요. 각 서비스 SDK/API 사용 | 커스텀 TCP/UDP 서버 구현 불가. WebRTC는 STUN/TURN 필요할 수 있음 |

### LLM Wrapper

- https://github.com/teddylee777/openai-api-kr
- https://github.com/teddylee777/langchain-kr
- https://devocean.sk.com/blog/techBoardDetail.do?ID=167407
- https://mastra.ai/docs

### Cross-Platform

- https://flutter.dev/
- https://reactnative.dev/
- https://docs.expo.dev/
- https://kotlinlang.org/multiplatform/
