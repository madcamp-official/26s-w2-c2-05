from datetime import date
from typing import Callable

from aiolimiter import AsyncLimiter

# 생성 모델 RPM/RPD 실측(AI Studio 대시보드) — 임베딩과 별도 쿼터라 limiter를
# 분리한다(DESIGN.md "처리 방식 확정" 절, 섹션7 TODO — 원래는 하나를 공유해서
# 임베딩이 생성 쿼터를 불필요하게 갉아먹는 버그가 있었음).
# 2026-07-13 T-02 실측 당시엔 gemini-2.5-flash-lite(RPM 10)였으나, T-08 실제
# 검증 중 이 모델이 신규 유저에게 폐기(404)된 걸 발견해 gemini-3.1-flash-lite
# (RPM 15)로 교체하며 값도 갱신함 — gemini_client.py의 GEMINI_MODEL 참고.
gemini_analyze_limiter = AsyncLimiter(max_rate=15, time_period=60)
gemini_embed_limiter = AsyncLimiter(max_rate=100, time_period=60)


class RpdCounter:
    """생성 모델의 일일 RPD 사전 차단용 로컬 카운터.

    aiolimiter(분당)와 별개로 자정에 리셋되는 일일 한도를 추적한다. 한도
    도달 시 Task 5(main.py)가 Gemini를 호출하지 않고 429를 반환하기 위해
    사전에 이 카운터로 확인한다 (2026-07-13 결정, DESIGN.md "처리 방식
    확정" 절). `clock`은 테스트에서 날짜를 주입하기 위한 훅.

    알려진 한계 (단일 프로세스·단일 VM 전제, DESIGN.md "배포 구조" 절과
    동일한 가정 — Redis 등 분산 인프라는 의도적으로 안 씀, 2026-07-13
    최종 브랜치 리뷰에서 확인):
    - 프로세스가 재시작되면 카운트가 0으로 리셋된다. 하루에 여러 번
      재시작/재배포되면 실제로는 하루 한도(500)보다 더 많은 Gemini 요청이
      나갈 수 있다.
    - `uvicorn --workers N`처럼 여러 프로세스로 띄우면 워커마다 이
      싱글턴을 따로 가지므로, 실질적인 하루 한도가 워커 수만큼 곱해진다.
      지금 배포는 단일 워커 전제라 문제 없지만, 워커를 늘릴 계획이 있다면
      이 카운터부터 손봐야 한다.
    """

    def __init__(self, limit: int = 500, clock: Callable[[], date] = date.today):
        self._limit = limit
        self._clock = clock
        self._count = 0
        self._reset_date = clock()

    def _maybe_reset(self) -> None:
        today = self._clock()
        if today != self._reset_date:
            self._count = 0
            self._reset_date = today

    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self._limit - self._count)

    def consume(self) -> bool:
        self._maybe_reset()
        if self._count >= self._limit:
            return False
        self._count += 1
        return True


# 생성 호출 전용 싱글턴 — 임베딩은 RPD 1,000이라 카운터 불필요.
# gemini-3.1-flash-lite RPD 500 실측(AI Studio, 2026-07-13, T-08 중 갱신)
gemini_analyze_rpd_counter = RpdCounter(limit=500)
