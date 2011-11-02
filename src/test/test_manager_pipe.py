from tempfile import NamedTemporaryFile
import unittest
import os
from pybreaker.manager.pipe import SpinningFifoManager, command_fifo_manager
import re
from ConfigParser import SafeConfigParser

class SpinningFifoManagerTest(unittest.TestCase):
    def setUp(self):
        self.input_path = NamedTemporaryFile(delete=False).name
        self.output_path = NamedTemporaryFile(delete=False).name
        self._set_up_manager()

    def _set_up_manager(self):
        self.manager = SpinningFifoManager(
            self.input_path, self.output_path, sleep_delay=.001)

        with self.manager.breaker('closed').context():
            pass

        for i in xrange(5):
            try:
                with self.manager.breaker('open').context():
                    raise NotImplementedError
            except:
                pass

        with self.manager.breaker('params').context('parm'):
            pass

    def tearDown(self):
        os.remove(self.input_path)
        os.remove(self.output_path)

    def _run_command(self, command):
        return command_fifo_manager(self.input_path, self.output_path, command, .005)

    def _clean_lines(self, lines):
        return [[word.strip() for word in re.split('\s\s+', line)] for line in lines]

    def test_status_succeeds(self):
        """SpinningFifoManager: it should list the status of all active circuit breakers
        """
        success, lines = self._run_command('status')
        print success, lines
        self.assertTrue(success)
        
        lines = self._clean_lines(lines)
        self.assertEquals(
            ['id', 'state', 'time until half_open', 'failure count', 'failures until open'],
            lines[0])
        self.assertEquals(
            ['closed', 'closed', 'None', '0', '5'],
            lines[1]
        )
        self.assertEquals(
            ['open', 'open', '5', 'None'],
            lines[2][0:2] + lines[2][3:]
        )
        self.assertEquals(
            ["('params', 'parm')", 'closed', 'None', '0', '5'],
            lines[3]
        )

    def test_status_single_breaker(self):
        """SpinningFifoManager: it should list the status of a specified circuit breaker
        """
        success, lines = self._run_command('status closed')
        self.assertTrue(success)
        
        lines = self._clean_lines(lines)
        self.assertEquals(
            ['id', 'state', 'time until half_open', 'failure count', 'failures until open'],
            lines[0])
        self.assertEquals(
            ['closed', 'closed', 'None', '0', '5'],
            lines[1]
        )

    def test_create_fifo_if_missing(self):
        """SpinningFifoManager: it should create a fifo pipe if it is missing
        """
        os.remove(self.input_path)
        self._set_up_manager()
        self.test_status_succeeds()

    def test_invalid_command(self):
        """SpinningFifoManager: it should flag invalid commands
        """
        success, lines = self._run_command('foobar')
        self.assertFalse(success)
        self.assertEquals(["Invalid command: foobar"], lines)

    def test_invalid_id(self):
        """SpinningFifoManager: it should flag invalid ids
        """
        success, lines = self._run_command('status foobar')
        self.assertFalse(success)
        self.assertEquals(["Invalid identifier: foobar"], lines)

    def test_change_status(self):
        """SpinningFifoManager: it should change circuit breaker states
        """
        success, lines = self._run_command("status ('params', 'parm')")
        self.assertTrue(success)
        lines = self._clean_lines(lines)
        self.assertEquals('closed', lines[1][1])

        for action, state in [
            ('open', 'open'),
            ('close', 'closed'),
            ('half_open', 'half_open'),
            ('force_open', 'forced_open'),
            ('force_closed', 'forced_closed')
        ]:
            success, lines = self._run_command(action + " ('params', 'parm')")
            self.assertTrue(success)
            self.assertEquals(["Changed `('params', 'parm')` state"], lines)
            success, lines = self._run_command("status ('params', 'parm')")
            self.assertTrue(success)
            lines = self._clean_lines(lines)
            self.assertEquals(state, lines[1][1])

    def test_from_config(self):
        """SpinningFifoManager: it should read configuration from a config file
        """
        config = SafeConfigParser()
        config.add_section('pybreaker')
        config.set('pybreaker', 'input_path', '/tmp/tmp_{pid}_in.pid')
        config.set('pybreaker', 'output_path', '/tmp/tmp_{pid}_out.pid')
        config.set('pybreaker', 'fail_max', '10')
        config.set('pybreaker', 'reset_timeout', '11')
        config.set('pybreaker', 'sleep_delay', '1.1')
        manager = SpinningFifoManager.from_config(config)

        self.assertEquals('/tmp/tmp_{pid}_in.pid'.format(pid=os.getpid()), manager._input_pipe)
        self.assertEquals('/tmp/tmp_{pid}_out.pid'.format(pid=os.getpid()), manager._output_file)
        self.assertEquals(10, manager._fail_max)
        self.assertEquals(11, manager._reset_timeout)
        self.assertEquals(1.1, manager.sleep_delay)
