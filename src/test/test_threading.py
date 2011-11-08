
import threading
import unittest
from time import sleep
from pybreaker import CircuitBreaker, CircuitBreakerListener
from types import MethodType

class CircuitBreakerThreadsTestCase(unittest.TestCase):
    """
    Tests to reproduce common synchronization errors on CircuitBreaker class.
    """

    def setUp(self):
        self.breaker = CircuitBreaker(fail_max=3000, reset_timeout=600)

    def _start_threads(self, target, n):
        """
        Starts `n` threads that calls `target` and waits for them to finish.
        """
        threads = [threading.Thread(target=target) for i in range(n)]
        [t.start() for t in threads]
        [t.join() for t in threads]

    def _mock_function(self, obj, func):
        """
        Replaces a bounded function in `self.breaker` by another.
        """
        setattr(obj, func.__name__, MethodType(func, self.breaker))

    def test_fail_thread_safety_context_manager(self):
        """CircuitBreaker: it should compute a failed call atomically to avoid race conditions, even when using context manager
        """
        def trigger_error():
            for n in range(500):
                try:
                    with self.breaker.context():
                        raise Exception()
                except: pass

        def _inc_counter(self):
            c = self._fail_counter
            sleep(0.00005)
            self._fail_counter = c + 1

        self._mock_function(self.breaker, _inc_counter)
        self._start_threads(trigger_error, 3)
        self.assertEqual(1500, self.breaker.fail_counter)

    def test_fail_thread_safety(self):
        """CircuitBreaker: it should compute a failed call atomically to avoid race conditions.
        """
        @self.breaker
        def err(): raise Exception()

        def trigger_error():
            for n in range(500):
                try: err()
                except: pass

        def _inc_counter(self):
            c = self._fail_counter
            sleep(0.00005)
            self._fail_counter = c + 1

        self._mock_function(self.breaker, _inc_counter)
        self._start_threads(trigger_error, 3)
        self.assertEqual(1500, self.breaker.fail_counter)

    def test_success_thread_safety(self):
        """CircuitBreaker: it should compute a successful call atomically to avoid race conditions.
        """
        @self.breaker
        def suc(): return True

        def trigger_success():
            for n in range(500):
                suc()

        class SuccessListener(CircuitBreakerListener):
            def success(self, cb):
                c = 0
                if hasattr(cb, '_success_counter'):
                    c = cb._success_counter
                sleep(0.00005)
                cb._success_counter = c + 1

        self.breaker.listeners.append(SuccessListener())
        self._start_threads(trigger_success, 3)
        self.assertEqual(1500, self.breaker._success_counter)

    def test_half_open_thread_safety(self):
        """CircuitBreaker: it should allow only one trial call when the circuit is half-open.
        """
        self.breaker.half_open()

        @self.breaker
        def err(): raise Exception()

        def trigger_failure():
            try: err()
            except: pass

        class StateListener(CircuitBreakerListener):
            def __init__(self):
                self._count = 0

            def before_call(self, cb, fun, *args, **kwargs):
                sleep(0.00005)

            def state_change(self, cb, old_state, new_state):
                if new_state == 'half_open':
                    self._count += 1

        state_listener = StateListener()
        self.breaker.listeners.append(state_listener)

        self._start_threads(trigger_failure, 5)
        self.assertEqual(1, state_listener._count)


    def test_fail_max_thread_safety(self):
        """CircuitBreaker: it should not allow more failed calls than 'fail_max' setting.
        """
        @self.breaker
        def err(): raise Exception()

        def trigger_error():
            for i in range(2000):
                try: err()
                except: pass

        class SleepListener(CircuitBreakerListener):
            def before_call(self, cb, func, *args, **kwargs):
                sleep(0.00005)

        self.breaker.listeners.append(SleepListener())
        self._start_threads(trigger_error, 3)
        self.assertEqual(self.breaker.fail_max, self.breaker.fail_counter)


