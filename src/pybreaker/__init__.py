#-*- coding:utf-8 -*-

"""
Threadsafe pure-Python implementation of the Circuit Breaker pattern, described
by Michael T. Nygard in his book 'Release It!'.

For more information on this and other patterns and best practices, buy the
book at http://pragprog.com/titles/mnee/release-it
"""

from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from fluidity import StateMachine, state, transition
from contextlib import contextmanager

import threading

__all__ = ('ParameterizedCircuitBreaker', 'CircuitBreaker', 'CircuitBreakerListener', 'CircuitBreakerError',)


class CircuitBreakerError(Exception):
    """
    When calls to a service fails because the circuit is open, this error is
    raised to allow the caller to handle this type of exception differently.
    """
    def __init__(self, params=None):
        super(CircuitBreakerError, self).__init__('Circuit breaker is open. Skipping operation')
        self.params = params

class ParameterizedCircuitBreaker(object):
    """
    Defines a set of circuit breakers to be used depending on the parameters of
    the call they protect
    """

    def __init__(self, fail_max=5, reset_timeout=60, exclude=None, listeners=None, exception=CircuitBreakerError):
        """
        Creates a new circuit breaker with the given parameters.

        `fail_max`: (int)
            The maximum numbers of consecutive failures before the circuit breaker opens

        `reset_timeout`: (float)
            The number of seconds before an open circuit breaker will switch to half_open

        `exclude`: (list of `Exception`s)
            A list of exceptions that shouldn't be counted as failures by this circuit breaker

        `listeners`: (list of `CircuitBreakerListener`s)
            A list of listeners to notify of circuit breaker events

        `exception`: (`Exception`)
            The exception to be raised when the `CircuitBreaker` is open
        """
        self.circuit_breakers = {}
        self._fail_max = fail_max
        self._reset_timeout = reset_timeout
        self._exclude = exclude
        self._listeners = listeners
        self._exception = exception

    def get_breaker(self, params):
        """
        Return the circuit_breaker for these parameters, creating it if it doesn't exist
        """
        if params in self.circuit_breakers:
            return self.circuit_breakers[params]
        else:
            def exception(*args, **kwargs):
                exc = self._exception(*args, **kwargs)
                exc.params = params
                return exc
            return self.circuit_breakers.setdefault(params,
                    CircuitBreaker(
                        self._fail_max,
                        self._reset_timeout,
                        self._exclude,
                        self._listeners,
                        exception))

    def call(self, func, params=None, *args, **kwargs):
        """
        Calls `call` method of the circuit breaker specified by `params`,
        using passing it the other arguments. `params` must be hashable
        """
        return self.get_breaker(params).call(func, *args, **kwargs)

    def __call__(self, arg_params=[], kwarg_params=[]):
        """
        Returns a wrapper that calls the function `func` according to the rules
        implemented by the current state of this circuit breaker.

        The parameters used to find the circuit breaker to use are
        the elements of args, indexed by the indices in arg_params,
        and the elements of kwargs, indexed by the indiceds of kwarg_params.
        """
        def wrapper(func):
            @wraps(func)
            def _wrapper(*args, **kwargs):
                params = (tuple(args[idx] for idx in arg_params), tuple((idx, kwargs.get(idx)) for idx in kwarg_params))
                return self.call(func, params, *args, **kwargs)
            return _wrapper
        return wrapper

    def context(self, params=None):
        """
        Use this ParameterizedCircuitBreaker as a context manager, specifying
        parameters
        """
        return self.get_breaker(params).context()

    def open(self, params=None):
        """
        Open the parameterized circuit breaker
        """
        return self.get_breaker(params).open()

    def close(self, params=None):
        """
        Close the parameterized circuit breaker
        """
        return self.get_breaker(params).close()

    def half_open(self, params=None):
        """
        Half-open the parameterized circuit breaker
        """
        return self.get_breaker(params).half_open()

    def force_open(self, params=None):
        """
        Force-open the parameterized circuit breaker
        """
        return self.get_breaker(params).force_open()

    def force_closed(self, params=None):
        """
        Force-closed the parameterized circuit breaker
        """
        return self.get_breaker(params).force_closed()


class UnsafeCircuitBreaker(StateMachine):
    """
    More abstractly, circuit breakers exists to allow one subsystem to fail
    without destroying the entire system.

    This is done by wrapping dangerous operations (typically integration points)
    with a component that can circumvent calls when the system is not healthy.

    This pattern is described by Michael T. Nygard in his book 'Release It!'.
    """

    STATES = ['open', 'closed', 'half_open', 'forced_open', 'forced_closed']

    initial_state = 'closed'
    for _state in STATES:
        state(_state)
    
    transition(from_='closed', event='attempt', to='closed')
    transition(from_='closed', event='success', to='closed',
        action='_reset_count')
    transition(from_='closed', event='error',   to='open',
        guard='_too_many_failures',
        action=['_reset_timer', '_raise_breaker_exception'])
    transition(from_='closed', event='error',   to='closed',
        guard='_not_too_many_failures')

    transition(from_='open', event='attempt', to='half_open',
        guard='_timeout_elapsed')
    transition(from_='open', event='attempt', to='open',
        guard='_timeout_remaining',
        action='_raise_breaker_exception')

    transition(from_='half_open', event='attempt', to='half_open')
    transition(from_='half_open', event='error',   to='open',
        action=['_reset_timer', '_raise_breaker_exception'])
    transition(from_='half_open', event='success', to='closed',
        action='_reset_count')

    transition(from_='forced_open', event='attempt', to='forced_open',
        action='_raise_breaker_exception')
    
    for event in ['attempt', 'success', 'error']:
        transition(from_='forced_closed', event=event, to='forced_closed')

    transition(from_=STATES, event='open',         to='open',
        action='_reset_timer')
    transition(from_=STATES, event='close',        to='closed',
        action='_reset_count')
    transition(from_=STATES, event='half_open',    to='half_open')
    transition(from_=STATES, event='force_open',   to='forced_open')
    transition(from_=STATES, event='force_closed', to='forced_closed')

    def __init__(self, fail_max=5, reset_timeout=60, exclude=None,
            listeners=None, exception=CircuitBreakerError):
        """
        Creates a new circuit breaker with the given parameters.

        `fail_max`: (int)
            The maximum numbers of consecutive failures before the circuit breaker opens

        `reset_timeout`: (float)
            The number of seconds before an open circuit breaker will switch to half_open

        `exclude`: (list of `Exception`s)
            A list of exceptions that shouldn't be counted as failures by this circuit breaker

        `listeners`: (list of `CircuitBreakerListener`s)
            A list of listeners to notify of circuit breaker events

        `exception`: (`Exception`)
            The exception to be raised when the `CircuitBreaker` is open
        """
        super(UnsafeCircuitBreaker, self).__init__()
        self._fail_counter = 0

        self.fail_max = fail_max
        self.reset_timeout = reset_timeout

        self.excluded_exceptions = list(exclude or [])
        self.listeners = list(listeners or [])
        self.exception = exception

    def changing_state(self, from_, to):
        """
        Overridden function that is called whenever a state transition happens
        """
        for listener in self.listeners:
            listener.state_change(self, from_, to)

    @property
    def fail_counter(self):
        """
        Returns the current number of consecutive failures.
        """

        return self._fail_counter

    def __call__(self, func):
        """
        Returns a wrapper that calls the function `func` according to the rules
        implemented by the current state of this circuit breaker.
        """
        @wraps(func)
        def _wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return _wrapper

    @contextmanager
    def context(self):
        """
        Enable a CircuitBreaker to be used as a context manager
        """
        self.attempt()
        try:
            yield
        except BaseException as exc:
            self._handle_error(exc)
        else:
            self._handle_success()

    def call(self, func, *args, **kwargs):
        """
        Calls `func` with the given `args` and `kwargs` according to the rules
        implemented by the current state of this circuit breaker.
        """
        with self.context():
            for listener in self.listeners:
                listener.before_call(self, func, *args, **kwargs)

            return func(*args, **kwargs)

    @property
    def timeout_remaining(self):
        """
        How long before an open circuit_breaker will flip to half_open, or None
        if the breaker isn't open
        """
        if self.current_state != 'open': return None

        timeout = timedelta(seconds=self.reset_timeout)
        return max(self._opened_at + timeout - datetime.now(), timedelta())

    @property
    def failure_count(self):
        """
        How many failures this breaker has seen since the last success
        """
        return self._fail_counter

    @property
    def failures_remaining(self):
        """
        How many failures are required to open this circuit, or None if the
        breaker isn't closed
        """
        if self.current_state != 'closed': return None
        return self.fail_max - self._fail_counter

    def _handle_error(self, exc):
        """
        Handles a failed call to the guarded operation.
        """
        if self._is_system_error(exc):
            self._fail_counter += 1
            self.error()
            for listener in self.listeners:
                listener.failure(self, exc)
        else:
            self._handle_success()
        raise

    def _handle_success(self):
        """
        Handles a successful call to the guarded operation.
        """
        self.success()
        for listener in self.listeners:
            listener.success(self)

    def _is_system_error(self, exception):
        """
        Returns whether the exception `exception` is considered a signal of
        system malfunction. Business exceptions should not cause this circuit
        breaker to open.
        """
        texc = type(exception)
        for exc in self.excluded_exceptions:
            if issubclass(texc, exc):
                return False
        return True

    def _reset_count(self):
        """
        An action that resets the failure count
        """
        self._fail_counter = 0

    def _not_too_many_failures(self):
        """
        A guard that returns true if failure count is less than the allowed max
        """
        return not self._too_many_failures()

    def _too_many_failures(self):
        """
        A guard that returns True if failure count has exceeded the allowed maximum
        """
        return self._fail_counter >= self.fail_max

    def _reset_timer(self):
        """
        An action that resets the timer that the open state uses to go to half_open
        """
        self._opened_at = datetime.now()

    def _raise_breaker_exception(self):
        """
        An action that raises the breaker exception
        """
        raise self.exception()

    def _timeout_elapsed(self):
        """
        A guard that returns True if the `reset_timeout` has elapsed since the
        breaker opened
        """
        remaining = self.timeout_remaining
        return remaining is None or remaining <= timedelta()

    def _timeout_remaining(self):
        """
        A guard that returns True if there is still time remaining before the
        `reset_timeout` is reached
        """
        return not self._timeout_elapsed()


class CircuitBreaker(object):
    __standard_locking__ = [
        'call', 'open', 'close', 'half_open', 'force_open',
        'force_closed', 'attempt', 'success', 'error']
    
    def __init__(self, fail_max=5, reset_timeout=60, exclude=None,
            listeners=None, exception=CircuitBreakerError):
        """
        Creates a new circuit breaker with the given parameters.

        `fail_max`: (int)
            The maximum numbers of consecutive failures before the circuit breaker opens

        `reset_timeout`: (float)
            The number of seconds before an open circuit breaker will switch to half_open

        `exclude`: (list of `Exception`s)
            A list of exceptions that shouldn't be counted as failures by this circuit breaker

        `listeners`: (list of `CircuitBreakerListener`s)
            A list of listeners to notify of circuit breaker events

        `exception`: (`Exception`)
            The exception to be raised when the `CircuitBreaker` is open
        """

        self.__dict__['cb'] = UnsafeCircuitBreaker(fail_max, reset_timeout, exclude,
            listeners, exception)

        self._lock = threading.RLock()

    @wraps(UnsafeCircuitBreaker.__call__)
    def __call__(self, *args, **kwargs):
        cb_wrapped = self.cb(*args, **kwargs)

        @wraps(cb_wrapped)
        def wrapper(*args, **kwargs):
            with self._lock:
                return cb_wrapped(*args, **kwargs)
        return wrapper

    @wraps(UnsafeCircuitBreaker.context)
    @contextmanager
    def context(self):
        with self._lock:
            with self.cb.context():
                yield

    def __getattr__(self, name):
        return getattr(self.cb, name)

    def __setattr__(self, name, value):
        return setattr(self.cb, name, value)

    def __delattr__(self, name):
        return delattr(self.cb, name)


def add_locked_function(method_name):
    @wraps(getattr(UnsafeCircuitBreaker, method_name))
    def fn(self, *args, **kwargs):
        with self._lock:
            return getattr(self.cb, method_name)(*args, **kwargs)
    setattr(CircuitBreaker, method_name, fn)


for method_name in CircuitBreaker.__standard_locking__:
    add_locked_function(method_name)


class CircuitBreakerListener(object):
    """
    Listener class used to plug code to a ``CircuitBreaker`` instance when
    certain events happen.
    """

    def before_call(self, cb, func, *args, **kwargs):
        """
        This callback function is called before the circuit breaker `cb` calls
        `fn`.
        """
        pass

    def failure(self, cb, exc):
        """
        This callback function is called when a function called by the circuit
        breaker `cb` fails.
        """
        pass

    def success(self, cb):
        """
        This callback function is called when a function called by the circuit
        breaker `cb` succeeds.
        """
        pass

    def state_change(self, cb, old_state, new_state):
        """
        This callback function is called when the state of the circuit breaker
        `cb` state changes.
        """
        pass
