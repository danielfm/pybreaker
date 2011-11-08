import unittest
from pybreaker.manager import CircuitBreakerManager, DuplicateCircuitBreaker
from datetime import timedelta


class CircuitBreakerManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = CircuitBreakerManager()

    def test_get_breaker_no_breaker(self):
        self.assertRaises(KeyError, self.manager.get_breaker, 'foo')

    def test_create_breaker_duplicate(self):
        self.manager.create_breaker('foo')
        self.assertRaises(DuplicateCircuitBreaker, self.manager.create_breaker, 'foo')

    def test_get_created_breaker(self):
        breaker = self.manager.create_breaker('foo')
        self.assertEquals(breaker, self.manager.breaker('foo'))

    def test_breaker_creates_breaker(self):
        self.assertRaises(KeyError, self.manager.get_breaker, 'foo')
        breaker = self.manager.breaker('foo')
        self.assertEquals(breaker, self.manager.get_breaker('foo'))

    def test_status(self):
        self.manager.breaker('open').open('open_parm')
        
        try:
            with self.manager.breaker('closed').context():
                raise NotImplementedError()
        except:
            pass
        
        self.manager.breaker('force_open').force_open('force_open_parm')

        status = self.manager.status()
        print status
        self.assertTrue(('open', 'open_parm') in status)
        self.assertTrue(('closed', None) in status)
        self.assertTrue(('force_open', 'force_open_parm') in status)

        self.assertEquals('open', status[('open', 'open_parm')]['state'])
        self.assertTrue(timedelta() < status[('open', 'open_parm')]['time until half_open'] < timedelta(60))
        self.assertEquals(0, status[('open', 'open_parm')]['failure count'])
        self.assertEquals(None, status[('open', 'open_parm')]['failures until open'])

        self.assertEquals('closed', status[('closed', None)]['state'])
        self.assertEquals(None, status[('closed', None)]['time until half_open'])
        self.assertEquals(1, status[('closed', None)]['failure count'])
        self.assertEquals(4, status[('closed', None)]['failures until open'])

        self.assertEquals('forced_open', status[('force_open', 'force_open_parm')]['state'])
        self.assertEquals(None, status[('force_open', 'force_open_parm')]['time until half_open'])
        self.assertEquals(0, status[('force_open', 'force_open_parm')]['failure count'])
        self.assertEquals(None, status[('force_open', 'force_open_parm')]['failures until open'])

    def test_open(self):
        with self.manager.breaker('foo').context():
            pass

        self.assertEquals('closed', self.manager.status()[('foo', None)]['state'])
        self.manager.open('foo', None)
        self.assertEquals('open', self.manager.status()[('foo', None)]['state'])

    def test_close(self):
        with self.manager.breaker('foo').context():
            pass

        self.manager.open('foo', None)
        self.assertEquals('open', self.manager.status()[('foo', None)]['state'])
        self.manager.close('foo', None)
        self.assertEquals('closed', self.manager.status()[('foo', None)]['state'])

    def test_half_open(self):
        with self.manager.breaker('foo').context():
            pass

        self.assertEquals('closed', self.manager.status()[('foo', None)]['state'])
        self.manager.half_open('foo', None)
        self.assertEquals('half_open', self.manager.status()[('foo', None)]['state'])

    def test_force_open(self):
        with self.manager.breaker('foo').context():
            pass

        self.assertEquals('closed', self.manager.status()[('foo', None)]['state'])
        self.manager.force_open('foo', None)
        self.assertEquals('forced_open', self.manager.status()[('foo', None)]['state'])

    def test_force_closed(self):
        with self.manager.breaker('foo').context():
            pass

        self.assertEquals('closed', self.manager.status()[('foo', None)]['state'])
        self.manager.force_closed('foo', None)
        self.assertEquals('forced_closed', self.manager.status()[('foo', None)]['state'])
