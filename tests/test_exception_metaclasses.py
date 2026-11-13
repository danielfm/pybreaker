"""Exception types with metaclasses must not be invoked as predicates."""

from abc import ABCMeta
from unittest.mock import Mock

import pytest

from pybreaker import (
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerListener,
)


class BusinessError(Exception, metaclass=ABCMeta):
    pass


class SpecificBusinessError(BusinessError):
    pass


class CountingMeta(type):
    calls = []

    def __call__(cls, *args, **kwargs):
        cls.calls.append(args)
        return super().__call__(*args, **kwargs)


class CountedBusinessError(Exception, metaclass=CountingMeta):
    pass


@pytest.mark.parametrize("excluded", [BusinessError, CountedBusinessError])
@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_unrelated_failures_still_open_circuit(excluded, error_type):
    listener = Mock(spec=CircuitBreakerListener)
    breaker = CircuitBreaker(fail_max=2, exclude=[excluded], listeners=[listener])
    failure = error_type("service unavailable")

    def fail():
        raise failure

    with pytest.raises(error_type) as first:
        breaker.call(fail)
    assert first.value is failure
    assert breaker.fail_counter == 1
    assert breaker.current_state == STATE_CLOSED
    with pytest.raises(CircuitBreakerError):
        breaker.call(fail)
    assert breaker.fail_counter == 2
    assert breaker.current_state == STATE_OPEN
    assert listener.failure.call_count == 2
    listener.success.assert_not_called()
    with pytest.raises(CircuitBreakerError):
        breaker.call(fail)
    assert listener.failure.call_count == 2


@pytest.mark.parametrize("error_type", [BusinessError, SpecificBusinessError, CountedBusinessError])
def test_matching_business_errors_reset_failures(error_type):
    listener = Mock(spec=CircuitBreakerListener)
    breaker = CircuitBreaker(fail_max=3, exclude=[BusinessError, CountedBusinessError], listeners=[listener])

    def fail(error):
        raise error

    with pytest.raises(RuntimeError):
        breaker.call(fail, RuntimeError("network"))
    assert breaker.fail_counter == 1
    error = error_type("business")
    with pytest.raises(error_type) as caught:
        breaker.call(fail, error)
    assert caught.value is error
    assert breaker.fail_counter == 0
    assert breaker.current_state == STATE_CLOSED
    listener.failure.assert_called_once()
    listener.success.assert_called_once_with(breaker)


def test_classification_does_not_instantiate_exception_class():
    CountedBusinessError.calls.clear()
    breaker = CircuitBreaker(exclude=[CountedBusinessError])
    assert breaker.is_system_error(RuntimeError("network")) is True
    assert CountedBusinessError.calls == []
    error = CountedBusinessError("business")
    CountedBusinessError.calls.clear()
    assert breaker.is_system_error(error) is False
    assert CountedBusinessError.calls == []


@pytest.mark.parametrize("matches", [False, True])
def test_callable_predicates_still_receive_original_exception(matches):
    predicate = Mock(return_value=matches)
    breaker = CircuitBreaker(exclude=[BusinessError, predicate])
    error = RuntimeError("network")
    assert breaker.is_system_error(error) is (not matches)
    predicate.assert_called_once_with(error)


@pytest.mark.parametrize("business", [False, True])
def test_half_open_trial_classification(business):
    listener = Mock(spec=CircuitBreakerListener)
    breaker = CircuitBreaker(exclude=[BusinessError], success_threshold=2, listeners=[listener])
    breaker.half_open()
    error = BusinessError("business") if business else RuntimeError("network")

    def fail():
        raise error

    if business:
        with pytest.raises(BusinessError) as caught:
            breaker.call(fail)
        assert caught.value is error
        assert breaker.current_state == STATE_HALF_OPEN
        assert breaker.success_counter == 1
        assert breaker.fail_counter == 0
        listener.success.assert_called_once_with(breaker)
        listener.failure.assert_not_called()
    else:
        with pytest.raises(CircuitBreakerError):
            breaker.call(fail)
        assert breaker.current_state == STATE_OPEN
        assert breaker.success_counter == 0
        assert breaker.fail_counter == 1
        listener.failure.assert_called_once_with(breaker, error)
        listener.success.assert_not_called()


def test_ordinary_exception_class_control():
    breaker = CircuitBreaker(exclude=[LookupError])
    assert breaker.is_system_error(KeyError("business")) is False
    assert breaker.is_system_error(RuntimeError("network")) is True


class StrictMeta(type):
    def __call__(cls):
        return super().__call__()


class StrictBusinessError(Exception, metaclass=StrictMeta):
    pass


def test_exception_constructor_is_not_a_filter():
    breaker = CircuitBreaker(fail_max=1, exclude=[StrictBusinessError])
    error = RuntimeError("service down")

    def fail():
        raise error

    with pytest.raises(CircuitBreakerError):
        breaker.call(fail)
    assert breaker.fail_counter == 1
    assert breaker.current_state == STATE_OPEN
