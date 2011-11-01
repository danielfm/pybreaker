#!/usr/bin/env python
#-*- coding:utf-8 -*-

from pybreaker import UnsafeCircuitBreaker, CircuitBreakerError, CircuitBreakerListener
from time import sleep

import unittest

class UnsafeCircuitBreakerTestCase(unittest.TestCase):
    """
    Tests for the UnsafeCircuitBreaker class.
    """

    def setUp(self):
        self.breaker = UnsafeCircuitBreaker()

    def test_default_params(self):
        """UnsafeCircuitBreaker: it should define smart defaults.
        """
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)
        self.assertEqual('closed', self.breaker.current_state)
        self.assertEqual([], self.breaker.excluded_exceptions)

    def test_new_with_custom_reset_timeout(self):
        """UnsafeCircuitBreaker: it should support a custom reset timeout value.
        """
        self.breaker = UnsafeCircuitBreaker(reset_timeout=30)
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(30, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)
        self.assertEqual([], self.breaker.excluded_exceptions)

    def test_new_with_custom_fail_max(self):
        """UnsafeCircuitBreaker: it should support a custom maximum number of failures.
        """
        self.breaker = UnsafeCircuitBreaker(fail_max=10)
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(10, self.breaker.fail_max)
        self.assertEqual([], self.breaker.excluded_exceptions)

    def test_new_with_custom_excluded_exceptions(self):
        """UnsafeCircuitBreaker: it should support a custom list of excluded exceptions.
        """
        self.breaker = UnsafeCircuitBreaker(exclude=[Exception])
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)
        self.assertEqual([Exception], self.breaker.excluded_exceptions)

    def test_fail_max_setter(self):
        """UnsafeCircuitBreaker: it should allow the user to set a new value for 'fail_max'.
        """
        self.assertEqual(5, self.breaker.fail_max)
        self.breaker.fail_max = 10
        self.assertEqual(10, self.breaker.fail_max)

    def test_reset_timeout_setter(self):
        """UnsafeCircuitBreaker: it should allow the user to set a new value for 'reset_timeout'.
        """
        self.assertEqual(60, self.breaker.reset_timeout)
        self.breaker.reset_timeout = 30
        self.assertEqual(30, self.breaker.reset_timeout)

    def test_call_with_no_args(self):
        """UnsafeCircuitBreaker: it should be able to invoke functions with no-args.
        """
        def func(): return True
        self.assertTrue(self.breaker.call(func))

    def test_call_with_args(self):
        """UnsafeCircuitBreaker: it should be able to invoke functions with args.
        """
        def func(arg1, arg2): return [arg1, arg2]
        self.assertEqual([42, 'abc'], self.breaker.call(func, 42, 'abc'))

    def test_call_with_kwargs(self):
        """UnsafeCircuitBreaker: it should be able to invoke functions with kwargs.
        """
        def func(**kwargs): return kwargs
        self.assertEqual({'a':1, 'b':2}, self.breaker.call(func, a=1, b=2))

    def test_successful_call(self):
        """UnsafeCircuitBreaker: it should keep the circuit closed after a successful call.
        """
        def func(): return True
        self.assertTrue(self.breaker.call(func))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_one_failed_call(self):
        """UnsafeCircuitBreaker: it should keep the circuit closed after a few failures.
        """
        def func(): raise NotImplementedError()
        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertEqual(1, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_one_successful_call_after_failed_call(self):
        """UnsafeCircuitBreaker: it should keep the circuit closed after few mixed outcomes.
        """
        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertEqual(1, self.breaker.fail_counter)

        self.assertTrue(self.breaker.call(suc))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_several_failed_calls(self):
        """UnsafeCircuitBreaker: it should open the circuit after many failures.
        """
        self.breaker = UnsafeCircuitBreaker(fail_max=3)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertEqual(3, self.breaker.fail_counter)
        self.assertEqual('open', self.breaker.current_state)

    def test_failed_call_after_timeout(self):
        """UnsafeCircuitBreaker: it should half-open the circuit after timeout.
        """
        self.breaker = UnsafeCircuitBreaker(fail_max=3, reset_timeout=0.01)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertEqual('closed', self.breaker.current_state)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertEqual(3, self.breaker.fail_counter)

        # Wait for timeout
        sleep(0.05)

        # Circuit should open again
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertEqual(4, self.breaker.fail_counter)
        self.assertEqual('open', self.breaker.current_state)

    def test_successful_after_timeout(self):
        """UnsafeCircuitBreaker: it should close the circuit when a call succeeds after timeout.
        """
        self.breaker = UnsafeCircuitBreaker(fail_max=3, reset_timeout=0.01)

        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertEqual('closed', self.breaker.current_state)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, err)
        self.assertRaises(CircuitBreakerError, self.breaker.call, suc)
        self.assertEqual(3, self.breaker.fail_counter)

        # Wait for timeout
        sleep(0.05)

        # Circuit should close again
        self.assertTrue(self.breaker.call(suc))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_failed_call_when_halfopen(self):
        """UnsafeCircuitBreaker: it should open the circuit when a call fails in half-open state.
        """
        def fun(): raise NotImplementedError()

        self.breaker.half_open()
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('half_open', self.breaker.current_state)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, fun)
        self.assertEqual(1, self.breaker.fail_counter)
        self.assertEqual('open', self.breaker.current_state)

    def test_successful_call_when_halfopen(self):
        """UnsafeCircuitBreaker: it should close the circuit when a call succeeds in half-open state.
        """
        def fun(): return True

        self.breaker.half_open()
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('half_open', self.breaker.current_state)

        # Circuit should open
        self.assertTrue(self.breaker.call(fun))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_close(self):
        """UnsafeCircuitBreaker: it should allow the circuit to be closed manually.
        """
        self.breaker = UnsafeCircuitBreaker(fail_max=3)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertEqual(3, self.breaker.fail_counter)
        self.assertEqual('open', self.breaker.current_state)

        # Circuit should close again
        self.breaker.close()
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_transition_events(self):
        """UnsafeCircuitBreaker: it should call the appropriate functions on every state transition.
        """
        class Listener(CircuitBreakerListener):
            def __init__(self):
                self.out = ''

            def state_change(self, cb, old_state, new_state):
                assert cb
                if old_state: self.out += old_state
                if new_state: self.out += '->' + new_state
                self.out += ','

        listener = Listener()
        self.breaker = UnsafeCircuitBreaker(listeners=(listener,))
        self.assertEqual('closed', self.breaker.current_state)

        self.breaker.open()
        self.assertEqual('open', self.breaker.current_state)

        self.breaker.half_open()
        self.assertEqual('half_open', self.breaker.current_state)

        self.breaker.close()
        self.assertEqual('closed', self.breaker.current_state)

        self.assertEqual('closed->open,open->half_open,half_open->closed,', listener.out)

    def test_call_events(self):
        """UnsafeCircuitBreaker: it should call the appropriate functions on every successful/failed call.
        """
        self.out = ''

        def suc(): return True
        def err(): raise NotImplementedError()

        class Listener(CircuitBreakerListener):
            def __init__(self):
                self.out = ''
            def before_call(self, cb, func, *args, **kwargs):
                assert cb
                self.out += '-'
            def success(self, cb):
                assert cb
                self.out += 'success'
            def failure(self, cb, exc):
                assert cb; assert exc
                self.out += 'failure'

        listener = Listener()
        self.breaker = UnsafeCircuitBreaker(listeners=(listener,))

        self.assertTrue(self.breaker.call(suc))
        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertEqual('-success-failure', listener.out)

    def test_excluded_exceptions(self):
        """UnsafeCircuitBreaker: it should ignore specific exceptions.
        """
        self.breaker = UnsafeCircuitBreaker(exclude=[LookupError])

        def err_1(): raise NotImplementedError()
        def err_2(): raise LookupError()
        def err_3(): raise KeyError()

        self.assertRaises(NotImplementedError, self.breaker.call, err_1)
        self.assertEqual(1, self.breaker.fail_counter)

        # LookupError is not considered a system error
        self.assertRaises(LookupError, self.breaker.call, err_2)
        self.assertEqual(0, self.breaker.fail_counter)

        self.assertRaises(NotImplementedError, self.breaker.call, err_1)
        self.assertEqual(1, self.breaker.fail_counter)

        # Should consider subclasses as well (KeyError is a subclass of LookupError)
        self.assertRaises(KeyError, self.breaker.call, err_3)
        self.assertEqual(0, self.breaker.fail_counter)

    def test_raise_custom_exception_on_open(self):
        """UnsafeCircuitBreaker: it should raise custom exceptions during open
        """
        class CustomError(CircuitBreakerError):
            pass

        self.breaker = UnsafeCircuitBreaker(fail_max=3, exception=CustomError)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CustomError, self.breaker.call, func)

    def test_raise_custom_exception_while_open(self):
        class CustomError(CircuitBreakerError):
            pass

        self.breaker = UnsafeCircuitBreaker(fail_max=3, exception=CustomError)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CustomError, self.breaker.call, func)
        self.assertEqual('open', self.breaker.current_state)
        self.assertRaises(CustomError, self.breaker.call, func)

    def test_raise_custom_exception_on_half_open_fail(self):
        class CustomError(CircuitBreakerError):
            pass

        self.breaker = UnsafeCircuitBreaker(fail_max=3, exception=CustomError, reset_timeout=.01)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CustomError, self.breaker.call, func)
        
        sleep(.05)
        self.assertRaises(CustomError, self.breaker.call, func)

    def test_decorator(self):
        """UnsafeCircuitBreaker: it should be a decorator.
        """
        @self.breaker
        def suc(value):
            "Docstring"
            return value

        @self.breaker
        def err(value):
            "Docstring"
            raise NotImplementedError()

        self.assertEqual('Docstring', suc.__doc__)
        self.assertEqual('Docstring', err.__doc__)
        self.assertEqual('suc', suc.__name__)
        self.assertEqual('err', err.__name__)

        self.assertRaises(NotImplementedError, err, True)
        self.assertEqual(1, self.breaker.fail_counter)

        self.assertTrue(suc(True))
        self.assertEqual(0, self.breaker.fail_counter)

    def test_forced_open(self):
        """UnsafeCircuitBreaker: when forced_open, it should always raise a circuit_breaker exception
        """
        self.breaker.force_open()
        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertRaises(CircuitBreakerError, self.breaker.call, suc)
        self.assertRaises(CircuitBreakerError, self.breaker.call, err)

    def test_forced_closed(self):
        """UnsafeCircuitBreaker: when forced_closed, it should never raise a circuit_breaker exception
        """
        self.breaker.force_closed()
        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertTrue(self.breaker.call(suc))
        for i in xrange(100):
            self.assertRaises(NotImplementedError, self.breaker.call, err)

if __name__ == '__main__':
    unittest.main()
