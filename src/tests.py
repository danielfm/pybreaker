#!/usr/bin/env python
#-*- coding:utf-8 -*-

from breaker import *

from random import random
from time import sleep
from StringIO import StringIO

import threading
import unittest


class _CircuitBreakerTestCase(unittest.TestCase):
    """
    Tests for the CircuitBreaker class.
    """

    def setUp(self):
        self.breaker = CircuitBreaker()

    def test_default_params(self):
        """CircuitBreaker: it should define smart defaults.
        """
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)
        self.assertEqual('closed', self.breaker.current_state)

    def test_new_with_custom_reset_timeout(self):
        """CircuitBreaker: it should support a custom reset timeout value.
        """
        self.breaker = CircuitBreaker(reset_timeout=30)
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(30, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)

    def test_new_with_custom_fail_max(self):
        """CircuitBreaker: it should support a custom maximum number of failures.
        """
        self.breaker = CircuitBreaker(fail_max=10)
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(10, self.breaker.fail_max)

    def test_fail_max_setter(self):
        """CircuitBreaker: it should allow the user to set a new value for 'fail_max'.
        """
        self.assertEqual(5, self.breaker.fail_max)
        self.breaker.fail_max = 10
        self.assertEqual(10, self.breaker.fail_max)

    def test_reset_timeout_setter(self):
        """CircuitBreaker: it should allow the user to set a new value for 'reset_timeout'.
        """
        self.assertEqual(60, self.breaker.reset_timeout)
        self.breaker.reset_timeout = 30
        self.assertEqual(30, self.breaker.reset_timeout)

    def test_call_with_no_args(self):
        """CircuitBreaker: it should be able to invoke functions with no-args.
        """
        def func(): return True
        self.assertTrue(self.breaker.call(func))

    def test_call_with_args(self):
        """CircuitBreaker: it should be able to invoke functions with args.
        """
        def func(arg1, arg2): return [arg1, arg2]
        self.assertEqual([42, 'abc'], self.breaker.call(func, 42, 'abc'))

    def test_call_with_kwargs(self):
        """CircuitBreaker: it should be able to invoke functions with kwargs.
        """
        def func(**kwargs): return kwargs
        self.assertEqual({'a':1, 'b':2}, self.breaker.call(func, a=1, b=2))

    def test_successful_call(self):
        """CircuitBreaker: it should keep the circuit closed after a successful call.
        """
        def func(): return True
        self.assertTrue(self.breaker.call(func))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_one_failed_call(self):
        """CircuitBreaker: it should keep the circuit closed after a few failures.
        """
        def func(): raise NotImplementedError()
        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertEqual(1, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_one_successful_call_after_failed_call(self):
        """CircuitBreaker: it should keep the circuit closed after few mixed outcomes.
        """
        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertEqual(1, self.breaker.fail_counter)

        self.assertTrue(self.breaker.call(suc))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_several_failed_calls(self):
        """CircuitBreaker: it should open the circuit after many failures.
        """
        self.breaker = CircuitBreaker(fail_max=3)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertEqual(3, self.breaker.fail_counter)
        self.assertEqual('open', self.breaker.current_state)

    def test_failed_call_after_timeout(self):
        """CircuitBreaker: it should half-open the circuit after timeout.
        """
        self.breaker = CircuitBreaker(fail_max=3, reset_timeout=0.5)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertEqual('closed', self.breaker.current_state)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, func)
        self.assertEqual(3, self.breaker.fail_counter)

        # Wait for timeout
        sleep(0.6)

        # Circuit should be half-open
        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertEqual(4, self.breaker.fail_counter)
        self.assertEqual('half-open', self.breaker.current_state)

    def test_successful_after_timeout(self):
        """CircuitBreaker: it should close the circuit when a call succeeds after timeout.
        """
        self.breaker = CircuitBreaker(fail_max=3, reset_timeout=0.5)

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
        sleep(0.6)

        # Circuit should be half-open
        self.assertEqual(True, self.breaker.call(suc))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('half-open', self.breaker.current_state)

    def test_failed_call_when_halfopen(self):
        """CircuitBreaker: it should open the circuit when a call fails in half-open state.
        """
        def fun(): raise NotImplementedError()

        self.breaker.half_open()
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('half-open', self.breaker.current_state)

        # Circuit should open
        self.assertRaises(CircuitBreakerError, self.breaker.call, fun)
        self.assertEqual(1, self.breaker.fail_counter)
        self.assertEqual('open', self.breaker.current_state)

    def test_successful_call_when_halfopen(self):
        """CircuitBreaker: it should close the circuit when a call succeeds in half-open state.
        """
        def fun(): return True

        self.breaker.half_open()
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('half-open', self.breaker.current_state)

        # Circuit should open
        self.assertEqual(True, self.breaker.call(fun))
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual('closed', self.breaker.current_state)

    def test_close(self):
        """CircuitBreaker: it should allow the circuit to be closed manually.
        """
        self.breaker = CircuitBreaker(fail_max=3)
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
        """CircuitBreaker: it should call the appropriate functions on every state transition.
        """
        out = StringIO()

        def on_change(cb, old, new):
            if old: out.write(old.name)
            if new: out.write('->' + new.name)
            out.write(',')

        self.breaker = CircuitBreaker(on_state_change=on_change)
        self.assertEqual('closed', self.breaker.current_state)

        self.breaker.open()
        self.assertEqual('open', self.breaker.current_state)

        self.breaker.half_open()
        self.assertEqual('half-open', self.breaker.current_state)

        self.breaker.close()
        self.assertEqual('closed', self.breaker.current_state)

        self.assertEqual('closed->open,open->half-open,half-open->closed,', out.getvalue())

    def test_call_events(self):
        """CircuitBreaker: it should call the appropriate functions on every successful/failed call.
        """
        out = StringIO()

        def suc(): return True
        def err(): raise NotImplementedError()

        def on_success(cb): out.write('-success')
        def on_failure(cb, exc): out.write('-failure')

        self.breaker = CircuitBreaker(on_success=on_success, on_failure=on_failure)

        self.assertEqual(True, self.breaker.call(suc))
        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertEqual('-success-failure', out.getvalue())

    def test_ignored_errors(self):
        """CircuitBreaker: it should ignore specific exceptions.
        """
        self.breaker = CircuitBreaker(ignore=[LookupError])

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


if __name__ == '__main__':
    unittest.main()
