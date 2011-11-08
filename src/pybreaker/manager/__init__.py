from pybreaker import CircuitBreakerError, ParameterizedCircuitBreaker
from threading import RLock

class DuplicateCircuitBreaker(Exception):
    pass

class CircuitBreakerManager(object):
    def __init__(self, fail_max=5, reset_timeout=60, exclude=None, listeners=None,
            exception=CircuitBreakerError):
        self._fail_max = fail_max
        self._reset_timeout = reset_timeout
        self._exclude = exclude
        self._listeners = listeners
        self._exception = exception
        self.breakers = {}
        self._lock = RLock()

    def create_breaker(self, ident, fail_max=None, reset_timeout=None, exclude=None,
            listeners=None, exception=None):
        """
        Creates a new managed breaker, overriding the specified default values,
        or raising DuplicateCircuitBreaker if the breaker already exists
        """

        with self._lock:
            if ident in self.breakers:
                raise DuplicateCircuitBreaker()

            breaker = ParameterizedCircuitBreaker(
                fail_max if fail_max is not None else self._fail_max,
                reset_timeout if reset_timeout is not None else self._reset_timeout,
                exclude if exclude is not None else self._exclude,
                listeners if listeners is not None else self._listeners,
                exception if exception is not None else self._exception,
            )
            self.breakers[ident] = breaker

            return breaker

    def get_breaker(self, ident):
        """
        Returns an already created breaker
        """
        with self._lock:
            return self.breakers[ident]

    def breaker(self, ident, fail_max=None, reset_timeout=None, exclude=None,
            listeners=None, exception=None):
        """
        Creates a new managed breaker, overriding the specified default values,
        or returns an existing one, if it exists
        """
        with self._lock:
            if ident in self.breakers:
                return self.get_breaker(ident)
            else:
                return self.create_breaker(ident, fail_max, reset_timeout, exclude,
                    listeners, exception)

    def status(self):
        """
        Return a dictionary mapping (`ident`, `param`) to breaker status data.
        The status data is a dictionary mapping:
            `state`: the current state of the circuit breaker
            `time until half_open`: a timedelta indicating how long before an open
                breaker switches to half_open
            `failure count`: the number of consecutive failures this breaker has had
            `failures until open`: the number of allowed consecutive failures before
                this breakers opens
        """
        return dict(
            ((ident, param), {
                'state': breaker.current_state,
                'time until half_open': breaker.timeout_remaining,
                'failure count': breaker.failure_count,
                'failures until open': breaker.failures_remaining,
            })
            for (ident, pbreaker) in self.breakers.items()
            for (param, breaker) in pbreaker.circuit_breakers.items()
        )

    def open(self, ident, params):
        """
        Open a particular breaker
        """
        self.get_breaker(ident).open(params)

    def close(self, ident, params):
        """
        close a particular breaker
        """
        self.get_breaker(ident).close(params)

    def half_open(self, ident, params):
        """
        half_open a particular breaker
        """
        self.get_breaker(ident).half_open(params)

    def force_open(self, ident, params):
        """
        force_open a particular breaker
        """
        self.get_breaker(ident).force_open(params)

    def force_closed(self, ident, params):
        """
        force_closed a particular breaker
        """
        self.get_breaker(ident).force_closed(params)
