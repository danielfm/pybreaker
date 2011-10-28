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
from traceback import format_stack

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
        def breaker():
            return CircuitBreaker(fail_max, reset_timeout, exclude, listeners, exception)

        self.circuit_breakers = defaultdict(breaker)
        self._exception = exception

    def call(self, func, params=None, *args, **kwargs):
        """
        Calls `call` method of the circuit breaker specified by `params`,
        using passing it the other arguments. `params` must be hashable
        """
        try:
            return self.circuit_breakers[params].call(func, *args, **kwargs)
        except self._exception as exc:
            exc.params = params
            raise

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



class UnsafeCircuitBreaker(StateMachine):
    """
    More abstractly, circuit breakers exists to allow one subsystem to fail
    without destroying the entire system.

    This is done by wrapping dangerous operations (typically integration points)
    with a component that can circumvent calls when the system is not healthy.

    This pattern is described by Michael T. Nygard in his book 'Release It!'.
    """

    STATES = ['open', 'closed', 'half_open']

    initial_state = 'closed'
    for _state in STATES:
        state(_state)
    
    transition(from_='closed', event='attempt', to='closed')
    transition(from_='closed', event='success', to='closed',
        action='reset_count')
    transition(from_='closed', event='error',   to='open',
        guard='too_many_failures',
        action=['reset_timer', 'raise_breaker_exception'])
    transition(from_='closed', event='error',   to='closed',
        guard='not_too_many_failures')

    transition(from_='open', event='attempt', to='half_open',
        guard='timeout_elapsed')
    transition(from_='open', event='attempt', to='open',
        guard='timeout_remaining',
        action='raise_breaker_exception')

    transition(from_='half_open', event='attempt', to='half_open')
    transition(from_='half_open', event='error',   to='open',
        action=['reset_timer', 'raise_breaker_exception'])
    transition(from_='half_open', event='success', to='closed',
        action='reset_count')

    transition(from_=STATES, event='open',      to='open',
        action='reset_timer')
    transition(from_=STATES, event='close',     to='closed',
        action='reset_count')
    transition(from_=STATES, event='half_open', to='half_open')

    def __init__(self, fail_max=5, reset_timeout=60, exclude=None,
            listeners=None, exception=CircuitBreakerError):
        """
        Creates a new circuit breaker with the given parameters.
        """
        super(UnsafeCircuitBreaker, self).__init__()
        self._fail_counter = 0

        self._fail_max = fail_max
        self._reset_timeout = reset_timeout

        self._excluded_exceptions = list(exclude or [])
        self._listeners = list(listeners or [])
        self._exception = exception

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

    @property
    def fail_max(self):
        """
        Returns the maximum number of failures tolerated before the circuit is
        opened.
        """
        return self._fail_max

    @fail_max.setter
    def fail_max(self, number):
        """
        Sets the maximum `number` of failures tolerated before the circuit is
        opened.
        """
        self._fail_max = number

    @property
    def reset_timeout(self):
        """
        Once this circuit breaker is opened, it should remain opened until the
        timeout period, in seconds, elapses.
        """
        return self._reset_timeout

    @reset_timeout.setter
    def reset_timeout(self, timeout):
        """
        Sets the `timeout` period, in seconds, this circuit breaker should be
        kept open.
        """
        self._reset_timeout = timeout

    @property
    def excluded_exceptions(self):
        """
        Returns the list of excluded exceptions, e.g., exceptions that should
        not be considered system errors by this circuit breaker.
        """
        return tuple(self._excluded_exceptions)

    def add_excluded_exception(self, exception):
        """
        Adds an exception to the list of excluded exceptions.
        """
        self._excluded_exceptions.append(exception)

    def add_excluded_exceptions(self, *exceptions):
        """
        Adds exceptions to the list of excluded exceptions.
        """
        for exc in exceptions:
            self.add_excluded_exception(exc)

    def remove_excluded_exception(self, exception):
        """
        Removes an exception from the list of excluded exceptions.
        """
        self._excluded_exceptions.remove(exception)

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

    def call(self, func, *args, **kwargs):
        """
        Calls `func` with the given `args` and `kwargs` according to the rules
        implemented by the current state of this circuit breaker.
        """
        ret = None

        self.attempt()
        for listener in self.listeners:
            listener.before_call(self, func, *args, **kwargs)

        try:
            ret = func(*args, **kwargs)
        except BaseException as exc:
            self._handle_error(exc)
        else:
            self._handle_success()
        return ret

    def _handle_error(self, exc):
        """
        Handles a failed call to the guarded operation.
        """
        if self.is_system_error(exc):
            self._fail_counter += 1
            self.error()
            for listener in self.listeners:
                listener.failure(self, exc)
        else:
            self._handle_success()
        raise exc

    def _handle_success(self):
        """
        Handles a successful call to the guarded operation.
        """
        self.success()
        for listener in self.listeners:
            listener.success(self)

    def __call__(self, func):
        """
        Returns a wrapper that calls the function `func` according to the rules
        implemented by the current state of this circuit breaker.
        """
        @wraps(func)
        def _wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return _wrapper

    @property
    def listeners(self):
        """
        Returns the registered listeners as a tuple.
        """
        return tuple(self._listeners)

    def add_listener(self, listener):
        """
        Registers a listener for this circuit breaker.
        """
        self._listeners.append(listener)

    def add_listeners(self, *listeners):
        """
        Registers listeners for this circuit breaker.
        """
        for listener in listeners:
            self.add_listener(listener)

    def remove_listener(self, listener):
        """
        Unregisters a listener of this circuit breaker.
        """
        self._listeners.remove(listener)

    def reset_count(self):
        """
        An action that resets the failure count
        """
        self._fail_counter = 0

    def not_too_many_failures(self):
        """
        A guard that returns true if failure count is less than the allowed max
        """
        return not self.too_many_failures()

    def too_many_failures(self):
        """
        A guard that returns True if failure count has exceeded the allowed maximum
        """
        return self._fail_counter >= self._fail_max

    def reset_timer(self):
        """
        An action that resets the timer that the open state uses to go to half_open
        """
        self._opened_at = datetime.now()

    def raise_breaker_exception(self):
        """
        An action that raises the breaker exception
        """
        raise self._exception()

    def timeout_elapsed(self):
        """
        A guard that returns True if the `reset_timeout` has elapsed since the
        breaker opened
        """
        timeout = timedelta(seconds=self.reset_timeout)
        return datetime.now() >= self._opened_at + timeout

    def timeout_remaining(self):
        """
        A guard that returns True if there is still time remaining before the
        `reset_timeout` is reached
        """
        return not self.timeout_elapsed()


class CircuitBreaker(object):
    def __init__(self, fail_max=5, reset_timeout=60, exclude=None,
            listeners=None, exception=CircuitBreakerError):

        self.__dict__['cb'] = UnsafeCircuitBreaker(fail_max, reset_timeout, exclude,
            listeners, exception)

        self._lock = threading.RLock()

    @wraps(UnsafeCircuitBreaker.call)
    def call(self, *args, **kwargs):
        with self._lock:
            return self.cb.call(*args, **kwargs)

    @wraps(UnsafeCircuitBreaker.__call__)
    def __call__(self, *args, **kwargs):
        cb_wrapped = self.cb(*args, **kwargs)

        @wraps(cb_wrapped)
        def wrapper(*args, **kwargs):
            with self._lock:
                return cb_wrapped(*args, **kwargs)
        return wrapper

    @wraps(UnsafeCircuitBreaker.open)
    def open(self):
        with self._lock:
            return self.cb.open()

    @wraps(UnsafeCircuitBreaker.close)
    def close(self):
        with self._lock:
            return self.cb.close()

    @wraps(UnsafeCircuitBreaker.half_open)
    def half_open(self):
        with self._lock:
            return self.cb.half_open()

    @wraps(UnsafeCircuitBreaker.attempt)
    def attempt(self):
        with self._lock:
            return self.cb.attempt()

    @wraps(UnsafeCircuitBreaker.success)
    def success(self):
        with self._lock:
            return self.cb.success()

    @wraps(UnsafeCircuitBreaker.error)
    def error(self):
        with self._lock:
            return self.cb.error()

    def __getattr__(self, name):
        return getattr(self.cb, name)

    def __setattr__(self, name, value):
        return setattr(self.cb, name, value)

    def __delattr__(self, name):
        return delattr(self.cb, name)



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
