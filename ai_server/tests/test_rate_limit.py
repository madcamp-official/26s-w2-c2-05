from datetime import date

import pytest
from ai_server.rate_limit import (
    RpdCounter,
    gemini_analyze_limiter,
    gemini_analyze_rpd_counter,
    gemini_embed_limiter,
)


def test_analyze_limiter_configured_at_15_per_60_seconds():
    assert gemini_analyze_limiter.max_rate == 15
    assert gemini_analyze_limiter.time_period == 60


def test_analyze_rpd_counter_configured_at_500():
    # gemini-3.1-flash-lite 실측(AI Studio, 2026-07-13): RPD 500. 예전
    # 모델(gemini-2.5-flash-lite, RPD 20)이 폐기되면서 갱신됨(T-08 중 발견).
    assert gemini_analyze_rpd_counter.remaining() == 500


def test_embed_limiter_configured_at_100_per_60_seconds():
    assert gemini_embed_limiter.max_rate == 100
    assert gemini_embed_limiter.time_period == 60


@pytest.mark.asyncio
async def test_analyze_limiter_can_be_acquired():
    async with gemini_analyze_limiter:
        pass  # 예외 없이 통과하면 정상 배선된 것


def test_rpd_counter_allows_up_to_limit_then_blocks():
    counter = RpdCounter(limit=20, clock=lambda: date(2026, 7, 13))
    for _ in range(20):
        assert counter.consume() is True
    assert counter.consume() is False
    assert counter.remaining() == 0


def test_rpd_counter_remaining_decrements_on_consume():
    counter = RpdCounter(limit=20, clock=lambda: date(2026, 7, 13))
    counter.consume()
    assert counter.remaining() == 19


def test_rpd_counter_resets_on_new_day():
    today = date(2026, 7, 13)
    counter = RpdCounter(limit=20, clock=lambda: today)
    for _ in range(20):
        counter.consume()
    assert counter.remaining() == 0

    today = date(2026, 7, 14)  # clock이 다음날을 가리키도록 이동
    assert counter.remaining() == 20
    assert counter.consume() is True
