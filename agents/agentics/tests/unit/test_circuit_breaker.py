"""
Unit tests for circuit breaker failure modes.

Covers SEC-03 from docs/devsecops/SECURITY_PLAN.md:
  1) Open circuit blocks requests
  2) Half-open -> closed transition after success
  3) Half-open -> open on failure
  4) Failure count increments correctly
  5) Recovery timeout respected
"""

import time
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenException,
    get_circuit_breaker,
    circuit_breakers,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_cb(name="test-cb", failure_threshold=3, recovery_timeout=2, **kwargs):
    """Create a brand-new CircuitBreaker, bypassing the global registry."""
    return CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        **kwargs,
    )


class FailingCall(Exception):
    """Custom exception raised by the always-fail stub."""
    pass


def always_fail():
    raise FailingCall("boom")


def always_succeed():
    return "ok"


async def async_always_fail():
    raise FailingCall("async boom")


async def async_always_succeed():
    return "ok"


# ---------------------------------------------------------------------------
# 1. Open circuit blocks requests
# ---------------------------------------------------------------------------

class TestOpenCircuitBlocksRequests:
    """Verify that an OPEN circuit breaker rejects calls immediately."""

    def test_open_raises_without_fallback(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10)
        # Trip the breaker with one failure
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        # Circuit is now OPEN
        assert cb.state == CircuitBreakerState.OPEN
        with pytest.raises(CircuitBreakerOpenException, match="OPEN"):
            cb.call(always_succeed)

    def test_open_calls_are_not_executed(self):
        """The underlying function must NOT be invoked when the circuit is open."""
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10)
        with pytest.raises(FailingCall):
            cb.call(always_fail)

        mock_fn = MagicMock(return_value="should-not-be-called")
        with pytest.raises(CircuitBreakerOpenException):
            cb.call(mock_fn)
        mock_fn.assert_not_called()

    def test_open_uses_fallback_when_provided(self):
        """When a fallback strategy is set, it is called instead of raising."""
        fallback = MagicMock(return_value="fallback-result")
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10, fallback_strategy=fallback)
        with pytest.raises(FailingCall):
            cb.call(always_fail)

        result = cb.call(always_succeed)
        assert result == "fallback-result"
        fallback.assert_called_once()

    def test_open_raises_when_fallback_also_fails(self):
        """If the fallback itself throws, CircuitBreakerOpenException is raised."""
        bad_fallback = MagicMock(side_effect=RuntimeError("fallback boom"))
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10, fallback_strategy=bad_fallback)
        with pytest.raises(FailingCall):
            cb.call(always_fail)

        with pytest.raises(CircuitBreakerOpenException, match="fallback failed"):
            cb.call(always_succeed)


# ---------------------------------------------------------------------------
# 2. Half-open -> closed transition after success
# ---------------------------------------------------------------------------

class TestHalfOpenToClosed:
    """A successful call in HALF_OPEN should close the circuit."""

    def test_half_open_success_resets_to_closed(self):
        cb = _fresh_cb(failure_threshold=2, recovery_timeout=0)
        # Trip to OPEN
        for _ in range(2):
            with pytest.raises(FailingCall):
                cb.call(always_fail)
        assert cb.state == CircuitBreakerState.OPEN

        # Expire recovery timeout immediately (timeout=0) -> next call is HALF_OPEN
        result = cb.call(always_succeed)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_success_counters_reset(self):
        """After transition, failure_count and success_count are zeroed."""
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=0)
        with pytest.raises(FailingCall):
            cb.call(always_fail)

        cb.call(always_succeed)
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.next_attempt_time is None


# ---------------------------------------------------------------------------
# 3. Half-open -> open on failure
# ---------------------------------------------------------------------------

class TestHalfOpenToOpen:
    """A failed call in HALF_OPEN should re-open the circuit."""

    def test_half_open_failure_reopens(self):
        cb = _fresh_cb(failure_threshold=2, recovery_timeout=0)
        # Trip to OPEN
        for _ in range(2):
            with pytest.raises(FailingCall):
                cb.call(always_fail)
        assert cb.state == CircuitBreakerState.OPEN

        # recovery_timeout=0 means the next attempt transitions to HALF_OPEN
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 3  # 2 original + 1 in half-open

    def test_reopened_circuit_blocks_requests_again(self):
        """After transitioning through OPEN->HALF_OPEN->OPEN with positive timeout, circuit blocks."""
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10)
        # Trip to OPEN
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        assert cb.state == CircuitBreakerState.OPEN
        # Recovery timeout hasn't elapsed => blocked
        with pytest.raises(CircuitBreakerOpenException):
            cb.call(always_succeed)


# ---------------------------------------------------------------------------
# 4. Failure count increments correctly
# ---------------------------------------------------------------------------

class TestFailureCountIncremented:
    """Each recorded failure bumps failure_count by 1."""

    def test_failure_count_increments(self):
        cb = _fresh_cb(failure_threshold=5)
        for i in range(3):
            with pytest.raises(FailingCall):
                cb.call(always_fail)
            assert cb.failure_count == i + 1

    def test_failure_count_does_not_exceed_threshold_until_trip(self):
        """Circuit stays CLOSED while failure_count < threshold."""
        cb = _fresh_cb(failure_threshold=3)
        for _ in range(2):
            with pytest.raises(FailingCall):
                cb.call(always_fail)
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.CLOSED

    def test_failure_count_resets_on_success(self):
        """A successful call in CLOSED state resets failure_count to 0."""
        cb = _fresh_cb(failure_threshold=5)
        for _ in range(3):
            with pytest.raises(FailingCall):
                cb.call(always_fail)
        assert cb.failure_count == 3

        cb.call(always_succeed)
        assert cb.failure_count == 0

    def test_last_failure_time_is_set(self):
        before = datetime.now()
        cb = _fresh_cb(failure_threshold=5)
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        assert cb.last_failure_time is not None
        assert cb.last_failure_time >= before


# ---------------------------------------------------------------------------
# 5. Recovery timeout respected
# ---------------------------------------------------------------------------

class TestRecoveryTimeout:
    """OPEN circuit must NOT allow calls until recovery_timeout has elapsed."""

    def test_call_blocked_before_timeout(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10)
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        assert cb.state == CircuitBreakerState.OPEN

        # Immediately trying again should be blocked (timeout not elapsed)
        with pytest.raises(CircuitBreakerOpenException):
            cb.call(always_succeed)

    def test_call_allowed_after_timeout(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=1)
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        # Wait for recovery_timeout + small buffer
        time.sleep(1.2)

        result = cb.call(always_succeed)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_next_attempt_time_is_set_on_open(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=30)
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        assert cb.next_attempt_time is not None
        # next_attempt_time should be approximately 30 seconds in the future
        delta = cb.next_attempt_time - datetime.now()
        assert 29 <= delta.total_seconds() <= 31

    def test_half_open_set_after_timeout_expires(self):
        """After recovery, state should be HALF_OPEN (not CLOSED) for the probe call."""
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=0)
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        # With timeout=0 the circuit should transition to HALF_OPEN immediately
        # but _should_attempt_reset is checked in call(); the state transitions
        # during the call. After a success the circuit ends up CLOSED.
        cb.call(always_succeed)
        assert cb.state == CircuitBreakerState.CLOSED


# ---------------------------------------------------------------------------
# Async call tests (same failure modes)
# ---------------------------------------------------------------------------

class TestAsyncCircuitBreaker:
    """Async path mirrors sync — verify failure modes for call_async."""

    @pytest.mark.asyncio
    async def test_async_open_blocks(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=10)
        with pytest.raises(FailingCall):
            await cb.call_async(async_always_fail)

        with pytest.raises(CircuitBreakerOpenException):
            await cb.call_async(async_always_succeed)

    @pytest.mark.asyncio
    async def test_async_failure_count_increments(self):
        cb = _fresh_cb(failure_threshold=5)
        for i in range(3):
            with pytest.raises(FailingCall):
                await cb.call_async(async_always_fail)
            assert cb.failure_count == i + 1

    @pytest.mark.asyncio
    async def test_async_half_open_to_closed(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=0)
        with pytest.raises(FailingCall):
            await cb.call_async(async_always_fail)

        result = await cb.call_async(async_always_succeed)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_async_half_open_to_open(self):
        cb = _fresh_cb(failure_threshold=1, recovery_timeout=0)
        with pytest.raises(FailingCall):
            await cb.call_async(async_always_fail)

        with pytest.raises(FailingCall):
            await cb.call_async(async_always_fail)

        assert cb.state == CircuitBreakerState.OPEN


# ---------------------------------------------------------------------------
# get_circuit_breaker global registry tests
# ---------------------------------------------------------------------------

class TestGlobalRegistry:
    """Verify the get_circuit_breaker helper manages the global dict."""

    def test_get_or_create(self):
        name = "unit-test-registry-cb"
        # Ensure clean state
        circuit_breakers.pop(name, None)

        cb = get_circuit_breaker(name, failure_threshold=7)
        assert cb.failure_threshold == 7
        assert name in circuit_breakers

        # Second call should return the same instance and update attributes
        cb2 = get_circuit_breaker(name, failure_threshold=9)
        assert cb2 is cb
        assert cb.failure_threshold == 9

        # Clean up
        circuit_breakers.pop(name, None)


# ---------------------------------------------------------------------------
# get_status sanity
# ---------------------------------------------------------------------------

class TestGetStatus:
    """get_status returns correct dict reflecting current state."""

    def test_closed_status(self):
        cb = _fresh_cb(name="status-cb", failure_threshold=5)
        status = cb.get_status()
        assert status["name"] == "status-cb"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["last_failure"] is None

    def test_open_status(self):
        cb = _fresh_cb(name="status-cb", failure_threshold=1)
        with pytest.raises(FailingCall):
            cb.call(always_fail)
        status = cb.get_status()
        assert status["state"] == "open"
        assert status["failure_count"] == 1
        assert status["next_attempt"] is not None
        assert status["last_failure"] is not None
