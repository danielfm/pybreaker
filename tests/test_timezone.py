from datetime import datetime, timezone

import pytest
from pybreaker import CircuitBreaker, CircuitBreakerError, CircuitOpenState


def test_before_call_timezone_aware():
    cb = CircuitBreaker(fail_max=1, reset_timeout=10)
    storage = cb._state_storage
    # Simulate open at a naive datetime
    naive_opened = datetime.now(timezone.utc)
    storage.opened_at = naive_opened

    state = CircuitOpenState(cb)
    # Should not raise TypeError
    with pytest.raises(CircuitBreakerError):
        state.before_call(lambda: None)
