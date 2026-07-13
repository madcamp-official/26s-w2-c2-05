from datetime import date
from typing import Callable

from aiolimiter import AsyncLimiter

# 2026-07-13 T-02 실측(AI Studio 대시보드): 생성(gemini-2.5-flash-lite) RPM 10,
# 임베딩(gemini-embedding-001) RPM 100 — 서로 다른 쿼터라 limiter를 분리한다
# (DESIGN.md "처리 방식 확정" 절, 섹션7 TODO — 원래는 하나를 공유해서 임베딩이
# 생성 쿼터를 불필요하게 갉아먹는 버그가 있었음).
gemini_analyze_limiter = AsyncLimiter(max_rate=10, time_period=60)
gemini_embed_limiter = AsyncLimiter(max_rate=100, time_period=60)


class RpdCounter:
    """생성 모델의 일일 RPD(20, 실측값) 사전 차단용 로컬 카운터.

    aiolimiter(분당)와 별개로 자정에 리셋되는 일일 한도를 추적한다. 한도
    도달 시 Task 5(main.py)가 Gemini를 호출하지 않고 429를 반환하기 위해
    사전에 이 카운터로 확인한다 (2026-07-13 결정, DESIGN.md "처리 방식
    확정" 절). `clock`은 테스트에서 날짜를 주입하기 위한 훅.
    """

    def __init__(self, limit: int = 20, clock: Callable[[], date] = date.today):
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


# 생성 호출 전용 싱글턴 — 임베딩은 RPD 1,000이라 카운터 불필요
gemini_analyze_rpd_counter = RpdCounter(limit=20)
