#!/usr/bin/env python
#-*- coding:utf-8 -*-

from pybreaker import *
from random import random
from time import sleep

import unittest


class ParameterizedCircuitBreakerTestCase(unittest.TestCase):
    """
    Tests for the ParameterizedCircuitBreaker class
    """
    def setUp(self):
        self.param_breaker = ParameterizedCircuitBreaker()

    def test_no_params(self):
        """ParameterizedCircuitBreaker: it should have a default parameter
        """
        breakers = self.param_breaker.circuit_breakers
        def func(): return True
        self.assertTrue(self.param_breaker.call(func))
        self.assertTrue(None in breakers)
        self.assertEqual(0, breakers[None].fail_counter)
        self.assertEqual('closed', breakers[None].current_state)

    def test_breaker_separation(self):
        """ParameterizedCircuitBreaker: it should have separate breakers for each unique parameter
        """
        breakers = self.param_breaker.circuit_breakers
        def pass_func(): return True
        def fail_func(): raise NotImplementedError()

        self.assertTrue(self.param_breaker.call(pass_func, 'pass'))
        self.assertTrue('pass' in breakers)
        self.assertEqual(0, breakers['pass'].fail_counter)
        self.assertEqual('closed', breakers['pass'].current_state)

        self.assertRaises(NotImplementedError, self.param_breaker.call, fail_func, 'fail')
        self.assertRaises(NotImplementedError, self.param_breaker.call, fail_func, 'fail')
        self.assertRaises(NotImplementedError, self.param_breaker.call, fail_func, 'fail')
        self.assertRaises(NotImplementedError, self.param_breaker.call, fail_func, 'fail')
        self.assertRaises(CircuitBreakerError, self.param_breaker.call, fail_func, 'fail')
        
        self.assertEqual(5, breakers['fail'].fail_counter)
        self.assertEqual('open',breakers['fail'].current_state)
        self.assertEqual(0, breakers['pass'].fail_counter)
        self.assertEqual('closed', breakers['pass'].current_state)

        self.assertTrue(self.param_breaker.call(pass_func, 'pass'))
        self.assertEqual(5, breakers['fail'].fail_counter)
        self.assertEqual('open',breakers['fail'].current_state)
        self.assertEqual(0, breakers['pass'].fail_counter)
        self.assertEqual('closed', breakers['pass'].current_state)

    def test_wrapped_function_args(self):
        """ParameterizedCircuitBreaker: it should set params based on function args
        """
        breakers = self.param_breaker.circuit_breakers

        @self.param_breaker([0,2])
        def func(arg0, arg1, arg2): return True
        key = ((0,2), ())
        self.assertTrue(func(0, 1, 2))
        self.assertTrue(key in breakers)
        self.assertEqual(0, breakers[key].fail_counter)
        self.assertEqual('closed', breakers[key].current_state)

    def test_wrapped_function_kwargs(self):
        """ParameterizedCircuitBreaker: it should set params based on function kwargs
        """
        breakers = self.param_breaker.circuit_breakers

        @self.param_breaker(kwarg_params=['arg0', 'arg2'])
        def func(arg0, arg1, arg2): return True
        key = ((), (('arg0', 0), ('arg2', 2)))
        self.assertTrue(func(arg0=0, arg1=1, arg2=2))
        self.assertTrue(key in breakers)
        self.assertEqual(0, breakers[key].fail_counter)
        self.assertEqual('closed', breakers[key].current_state)

    def test_custom_exception_parameters_set(self):
        """ParameterizedCircuitBreaker: it should set the params on the custom exceptions raised
        """
        class CustomError(CircuitBreakerError):
            pass

        self.param_breaker = ParameterizedCircuitBreaker(fail_max=3, exception=CustomError)
        def func(): raise NotImplementedError()
        self.assertRaises(NotImplementedError, self.param_breaker.call, func, 'fail')
        self.assertRaises(NotImplementedError, self.param_breaker.call, func, 'fail')
        try:
            self.param_breaker.call(func, 'fail')
        except CustomError as exc:
            self.assertEquals('fail', exc.params)


class CircuitBreakerTestCase(unittest.TestCase):
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
        self.assertEqual([], self.breaker.excluded_exceptions)

    def test_new_with_custom_reset_timeout(self):
        """CircuitBreaker: it should support a custom reset timeout value.
        """
        self.breaker = CircuitBreaker(reset_timeout=30)
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(30, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)
        self.assertEqual([], self.breaker.excluded_exceptions)

    def test_new_with_custom_fail_max(self):
        """CircuitBreaker: it should support a custom maximum number of failures.
        """
        self.breaker = CircuitBreaker(fail_max=10)
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(10, self.breaker.fail_max)
        self.assertEqual([], self.breaker.excluded_exceptions)

    def test_new_with_custom_excluded_exceptions(self):
        """CircuitBreaker: it should support a custom list of excluded exceptions.
        """
        self.breaker = CircuitBreaker(exclude=[Exception])
        self.assertEqual(0, self.breaker.fail_counter)
        self.assertEqual(60, self.breaker.reset_timeout)
        self.assertEqual(5, self.breaker.fail_max)
        self.assertEqual([Exception], self.breaker.excluded_exceptions)

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
        self.breaker = CircuitBreaker(fail_max=3, reset_timeout=0.01)
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
        """CircuitBreaker: it should close the circuit when a call succeeds after timeout.
        """
        self.breaker = CircuitBreaker(fail_max=3, reset_timeout=0.01)

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
        """CircuitBreaker: it should open the circuit when a call fails in half-open state.
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
        """CircuitBreaker: it should close the circuit when a call succeeds in half-open state.
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
        class Listener(CircuitBreakerListener):
            def __init__(self):
                self.out = ''

            def state_change(self, cb, old_state, new_state):
                assert cb
                if old_state: self.out += old_state
                if new_state: self.out += '->' + new_state
                self.out += ','

        listener = Listener()
        self.breaker = CircuitBreaker(listeners=(listener,))
        self.assertEqual('closed', self.breaker.current_state)

        self.breaker.open()
        self.assertEqual('open', self.breaker.current_state)

        self.breaker.half_open()
        self.assertEqual('half_open', self.breaker.current_state)

        self.breaker.close()
        self.assertEqual('closed', self.breaker.current_state)

        self.assertEqual('closed->open,open->half_open,half_open->closed,', listener.out)

    def test_call_events(self):
        """CircuitBreaker: it should call the appropriate functions on every successful/failed call.
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
        self.breaker = CircuitBreaker(listeners=(listener,))

        self.assertTrue(self.breaker.call(suc))
        self.assertRaises(NotImplementedError, self.breaker.call, err)
        self.assertEqual('-success-failure', listener.out)

    def test_excluded_exceptions(self):
        """CircuitBreaker: it should ignore specific exceptions.
        """
        self.breaker = CircuitBreaker(exclude=[LookupError])

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
        """CircuitBreaker: it should raise custom exceptions during open
        """
        class CustomError(CircuitBreakerError):
            pass

        self.breaker = CircuitBreaker(fail_max=3, exception=CustomError)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CustomError, self.breaker.call, func)

    def test_raise_custom_exception_while_open(self):
        class CustomError(CircuitBreakerError):
            pass

        self.breaker = CircuitBreaker(fail_max=3, exception=CustomError)
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

        self.breaker = CircuitBreaker(fail_max=3, exception=CustomError, reset_timeout=.01)
        def func(): raise NotImplementedError()

        self.assertRaises(NotImplementedError, self.breaker.call, func)
        self.assertRaises(NotImplementedError, self.breaker.call, func)

        # Circuit should open
        self.assertRaises(CustomError, self.breaker.call, func)
        
        sleep(.05)
        self.assertRaises(CustomError, self.breaker.call, func)

    def test_decorator(self):
        """CircuitBreaker: it should be a decorator.
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
        """CircuitBreaker: when forced_open, it should always raise a circuit_breaker exception
        """
        self.breaker.force_open()
        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertRaises(CircuitBreakerError, self.breaker.call, suc)
        self.assertRaises(CircuitBreakerError, self.breaker.call, err)

    def test_forced_closed(self):
        """CircuitBreaker: when forced_closed, it should never raise a circuit_breaker exception
        """
        self.breaker.force_closed()
        def suc(): return True
        def err(): raise NotImplementedError()

        self.assertTrue(self.breaker.call(suc))
        for i in xrange(100):
            self.assertRaises(NotImplementedError, self.breaker.call, err)

import threading
from types import MethodType

class CircuitBreakerThreadsTestCase(unittest.TestCase):
    """
    Tests to reproduce common synchronization errors on CircuitBreaker class.
    """

    def setUp(self):
        self.breaker = CircuitBreaker(fail_max=3000, reset_timeout=1)

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
        self.breaker = CircuitBreaker(fail_max=1, reset_timeout=0.01)

        self.breaker.open()
        sleep(0.01)

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


if __name__ == '__main__':
    unittest.main()
