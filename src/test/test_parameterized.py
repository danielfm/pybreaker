
import unittest
from pybreaker import ParameterizedCircuitBreaker, CircuitBreakerError

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

    def test_custom_exception_parameters_set_context_manager(self):
        """ParameterizedCircuitBreaker: it should set the params on the custom exceptions raised, even with a context manager
        """
        class CustomError(CircuitBreakerError):
            pass

        self.param_breaker = ParameterizedCircuitBreaker(fail_max=3, exception=CustomError)

        def fail_breaker():
            with self.param_breaker.context('fail'):
                raise NotImplementedError()

        self.assertRaises(NotImplementedError, fail_breaker)
        self.assertRaises(NotImplementedError, fail_breaker)
        try:
            fail_breaker()
        except CustomError as exc:
            self.assertEquals('fail', exc.params)

    def test_open(self):
        """ParameterizedCircuitBreaker: it should open the parameterized breaker
        """
        self.assertEquals('closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)
        self.param_breaker.open('foo')
        self.assertEquals('open', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)

    def test_close(self):
        """ParameterizedCircuitBreaker: it should close the parameterized breaker
        """
        self.assertEquals('closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)
        self.param_breaker.open('foo')
        self.assertEquals('open', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)
        self.param_breaker.close('foo')
        self.assertEquals('closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)

    def test_half_open(self):
        """ParameterizedCircuitBreaker: it should half_open the parameterized breaker
        """
        self.assertEquals('closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)
        self.param_breaker.half_open('foo')
        self.assertEquals('half_open', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)

    def test_force_open(self):
        """ParameterizedCircuitBreaker: it should force_open the parameterized breaker
        """
        self.assertEquals('closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)
        self.param_breaker.force_open('foo')
        self.assertEquals('forced_open', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)

    def test_force_closed(self):
        """ParameterizedCircuitBreaker: it should force_closed the parameterized breaker
        """
        self.assertEquals('closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)
        self.param_breaker.force_closed('foo')
        self.assertEquals('forced_closed', self.param_breaker.get_breaker('foo').current_state)
        self.assertEquals('closed', self.param_breaker.get_breaker('bar').current_state)

