#-*- coding:utf-8 -*-

"""
Threadsafe pure-Python implementation of the Circuit Breaker pattern, described
by Michael T. Nygard in his book 'Release It!'.

For more information on this and other patterns and best practices, buy the
book at http://pragprog.com/titles/mnee/release-it
"""

import __future__

from datetime import datetime, timedelta
import threading

__all__ = ('CircuitBreaker', 'CircuitBreakerError')


class CircuitBreaker(object):
    """
    More abstractly, circuit breakers exists to allow one subsystem to fail
    without destroying the entire system.

    This is done by wrapping dangerous operations (typically integration points)
    with a component that can circumvent calls when the system is not healthy.

    This pattern is described by Michael T. Nygard in his book 'Release It!'.
    """

    def __init__(self, fail_max=5, reset_timeout=60, exclude=None,
            on_failure=None, on_success=None, on_state_change=None):
        """
        Creates a new circuit breaker with the given parameters.
        """
        self._fail_max = fail_max
        self._reset_timeout = reset_timeout
        self._excluded_exceptions = tuple(exclude or ())

        self._on_state_change = on_state_change
        self._on_failure = on_failure
        self._on_success = on_success

        self._lock = threading.RLock()
        self._state = CircuitClosedState(self)
        self._fail_counter = 0

    def _get_fail_counter(self):
        """
        Returns the current number of consecutive failures.
        """
        return self._fail_counter

    def _get_fail_max(self):
        """
        Returns the maximum number of failures tolerated before the circuit is
        opened.
        """
        return self._fail_max

    def _set_fail_max(self, number):
        """
        Sets the maximum `number` of failures tolerated before the circuit is
        opened.
        """
        self._fail_max = number

    def _get_reset_timeout(self):
        """
        Once this circuit breaker is opened, it should remain opened until the
        timeout period, in seconds, elapses.
        """
        return self._reset_timeout

    def _set_reset_timeout(self, timeout):
        """
        Sets the `timeout` period, in seconds, this circuit breaker should be
        kept open.
        """
        self._reset_timeout = timeout

    def _get_state(self):
        """
        Returns the current state of this circuit breaker.
        """
        return self._state

    def _get_current_state(self):
        """
        Returns a string that identifies this circuit breaker's state, i.e.,
        'closed', 'open', 'half-open'.
        """
        return self._state.name

    def _get_excluded_exc(self):
        """
        Returns the list of excluded exceptions, e.g., exceptions that should
        not be considered system errors by this circuit breaker.
        """
        return self._excluded_exceptions

    def _set_excluded_exc(self, exc_classes):
        """
        Sets the list of excluded exceptions, e.g., exceptions that should not
        be considered system errors by this circuit breaker.
        """
        self._excluded_exceptions = tuple(exc_classes or ())

    def is_system_error(self, exception):
        """
        Returns whether the exception `exception` is considered a signal of
        system malfunction. Business exceptions should not cause this circuit
        breaker to open.
        """
        texc = type(exception)
        for exc in self._excluded_exceptions:
            if issubclass(texc, exc):
                return False
        return True

    def synchronized(self, func, *args, **kwargs):
        """
        Runs the function `func` with the given `args` and `kwargs` in
        isolation, using a reentrant lock to do so. Use this function to
        guarantee that any changes in this circuit breaker done by `func` are
        thread safe.
        """
        try:
            self._lock.acquire()
            ret = func(*args, **kwargs)
        finally:
            self._lock.release()
        return ret

    def call(self, func, *args, **kwargs):
        """
        Calls `func` with the given `args` and `kwargs` according to the rules
        implemented by the current state of this circuit breaker.
        """
        return self._state.call(func, *args, **kwargs)

    def open(self):
        """
        Opens the circuit, e.g., the following calls will immediately fail
        until timeout elapses.
        """
        def _open():
            self._state = CircuitOpenState(self, self._state, notify=True)
        self.synchronized(_open)

    def half_open(self):
        """
        Half-opens the circuit, e.g. lets the following call pass through and
        opens the circuit if the call fails (or closes the circuit if the call
        succeeds).
        """
        def _half_open():
            self._state = CircuitHalfOpenState(self, self._state, notify=True)
        self.synchronized(_half_open)

    def close(self):
        """
        Closes the circuit, e.g. lets the following calls execute as usual.
        """
        def _close():
            self._state = CircuitClosedState(self, self._state, notify=True)
        self.synchronized(_close)

    def on_state_change(self, old_state, new_state):
        """
        Override this method to be notified when the circuit state changes.
        """
        if hasattr(self._on_state_change, '__call__'):
            return self._on_state_change(self, old_state, new_state)

    def on_failure(self, exc):
        """
        Override this method to be notified when a call to the guarded
        operation fails.
        """
        if hasattr(self._on_failure, '__call__'):
            return self._on_failure(self, exc)

    def on_success(self):
        """
        Override this method to be notified when a call to the guarded
        operation succeeds.
        """
        if hasattr(self._on_success, '__call__'):
            return self._on_success(self)

    def __call__(self, func):
        """
        Returns a wrapper that calls the function `func` according to the rules
        implemented by the current state of this circuit breaker.
        """
        def _wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return _wrapper

    # Properties
    excluded_exceptions = property(_get_excluded_exc, _set_excluded_exc)
    fail_counter        = property(_get_fail_counter)
    fail_max            = property(_get_fail_max, _set_fail_max)
    reset_timeout       = property(_get_reset_timeout, _set_reset_timeout)
    state               = property(_get_state)
    current_state       = property(_get_current_state)


class CircuitBreakerState(object):
    """
    Implements the behavior needed by all circuit breaker states.
    """

    def __init__(self, cb, name):
        """
        Creates a new instance associated with the circuit breaker `cb` and
        identified by `name`.
        """
        self._breaker = cb
        self._name = name

    def get_name(self):
        """
        Returns a human friendly name that identifies this state.
        """
        return self._name

    def _handle_error(self, exc):
        """
        Handles a failed call to the guarded operation.
        """
        if self._breaker.is_system_error(exc):
            self._breaker._fail_counter += 1
            self.on_failure(exc)
            self._breaker.on_failure(exc)
        else:
            self._handle_success()
        raise exc

    def _handle_success(self):
        """
        Handles a successful call to the guarded operation.
        """
        self._breaker._fail_counter = 0
        self.on_success()
        self._breaker.on_success()

    def call(self, func, *args, **kwargs):
        """
        Calls `func` with the given `args` and `kwargs`, and updates the
        circuit breaker state according to the result.
        """
        ret = None
        self.before_call()
        try:
            ret = func(*args, **kwargs)
        except BaseException as e:
            self._breaker.synchronized(self._handle_error, e)
        else:
            self._breaker.synchronized(self._handle_success)
        return ret

    def before_call(self):
        """
        Override this method to be notified before a call to the guarded
        operation is attempted.
        """
        pass

    def on_success(self):
        """
        Override this method to be notified when a call to the guarded
        operation succeeds.
        """
        pass

    def on_failure(self, exc):
        """
        Override this method to be notified when a call to the guarded
        operation fails.
        """
        pass

    # Properties
    name = property(get_name)


class CircuitClosedState(CircuitBreakerState):
    """
    In the normal "closed" state, the circuit breaker executes operations as
    usual. If the call succeeds, nothing happens. If it fails, however, the
    circuit breaker makes a note of the failure.

    Once the number of failures exceeds a threshold, the circuit breaker trips
    and "opens" the circuit.
    """

    def __init__(self, cb, prev_state=None, notify=False):
        """
        Moves the given circuit breaker `cb` to the "closed" state.
        """
        CircuitBreakerState.__init__(self, cb, 'closed')
        self._breaker._fail_counter = 0
        if notify:
            self._breaker.on_state_change(prev_state, self)

    def on_failure(self, exc):
        """
        Moves the circuit breaker to the "open" state once the failures
        threshold is reached.
        """
        if self._breaker._fail_counter >= self._breaker.fail_max:
            self._breaker.open()
            raise CircuitBreakerError('Failures threshold reached, circuit breaker opened')


class CircuitOpenState(CircuitBreakerState):
    """
    When the circuit is "open", calls to the circuit breaker fail immediately,
    without any attempt to execute the real operation. This is indicated by the
    ``CircuitBreakerError`` exception.

    After a suitable amount of time, the circuit breaker decides that the
    operation has a chance of succeeding, so it goes into the "half-open" state.
    """

    def __init__(self, cb, prev_state=None, notify=False):
        """
        Moves the given circuit breaker `cb` to the "open" state.
        """
        CircuitBreakerState.__init__(self, cb, 'open')
        self.opened_at = datetime.now()
        if notify:
            self._breaker.on_state_change(prev_state, self)

    def before_call(self):
        """
        After the timeout elapses, move the circuit breaker to the "half-open"
        state; otherwise, raises ``CircuitBreakerError`` without any attempt
        to execute the real operation.
        """
        timeout = timedelta(seconds=self._breaker.reset_timeout)
        if datetime.now() < self.opened_at + timeout:
            raise CircuitBreakerError('Timeout not elapsed yet, circuit breaker still open')
        else:
            self._breaker.half_open()


class CircuitHalfOpenState(CircuitBreakerState):
    """
    In the "half-open" state, the next call to the circuit breaker is allowed
    to execute the dangerous operation. Should the call succeed, the circuit
    breaker resets and returns to the "closed" state. If this trial call fails,
    however, the circuit breaker returns to the "open" state until another
    timeout elapses.
    """

    def __init__(self, cb, prev_state=None, notify=False):
        """
        Moves the given circuit breaker `cb` to the "half-open" state.
        """
        CircuitBreakerState.__init__(self, cb, 'half-open')
        if notify:
            self._breaker.on_state_change(prev_state, self)

    def on_failure(self, exc):
        """
        Opens the circuit breaker.
        """
        self._breaker.open()
        raise CircuitBreakerError('Trial call failed, circuit breaker opened')

    def on_success(self):
        """
        Closes the circuit breaker.
        """
        self._breaker.close()


class CircuitBreakerError(Exception):
    """
    When calls to a service fails because the circuit is open, this error is
    raised to allow the caller to handle this type of exception differently.
    """
    pass
