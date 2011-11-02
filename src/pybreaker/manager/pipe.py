from pybreaker.manager import CircuitBreakerManager, CircuitBreakerError
from time import sleep
from threading import Thread
import os
import logging
from argparse import ArgumentParser
import sys
from ConfigParser import SafeConfigParser

log = logging.getLogger(__file__)

class InvalidIdentifier(Exception):
    def __init__(self, ident):
        super(InvalidIdentifier, self).__init__("Invalid identifier: {id}".format(id=ident))

class SpinningFifoManager(CircuitBreakerManager):

    @classmethod
    def from_config(cls, config_parser, exclude=None, listeners=None,
            exception=CircuitBreakerError):
        """
        Create a new SpinningFifoManager using values from a configuration file

        Configs used are:

        [pybreaker]
            input_path = <path>
            output_path = <path>
            fail_max = <int, default 5>
            reset_timout = <float, default 60>
            sleep_delay = <float, default .1>

        `input_path`: the path to read incoming commands from. Works best with a FIFO
            pipe. If the path contains the string {pid}, the current process id will
            be substituted into it

        `output_path`: the path to write command results. Each result will overwrite
            the previous. If the path contains the string {pid}, the current process id
            will be substituted into it

        `fail_max`: the maximum number of times an action can fail before the breaker
            opens

        `reset_timeout`: the number of seconds that it takes a breaker to reset from
            open to half_open

        `sleep_delay`: the number of seconds the i/o thread will sleep after not
            finding a command to executed
        """
        return cls(
            config_parser.get('pybreaker', 'input_path').format(pid=os.getpid()),
            config_parser.get('pybreaker', 'output_path').format(pid=os.getpid()),
            int(config_parser.get('pybreaker', 'fail_max', 5)),
            float(config_parser.get('pybreaker', 'reset_timeout', 60)),
            exclude,
            listeners,
            exception,
            float(config_parser.get('pybreaker', 'sleep_delay', .1)),
        )

    def __init__(self, input_pipe, output_file, fail_max=5, reset_timeout=60,
            exclude=None, listeners=None, exception=CircuitBreakerError,
            sleep_delay=.1):
        """
        Create a new SpinningFifoManager. All arguments not listed are as for a normal
        CircuitBreakerManager

        `input_pipe`: the path to read incoming commands from. Works best with a FIFO
            pipe

        `output_file`: the path to write command results. Each result will overwrite
            the previous

        `sleep_delay`: the number of seconds the i/o thread will sleep after not
            finding a command to executed

        This manager spawns a daemonized thread that watches the `input_pipe` for
        commands, and then dumps results from those commands into `output_file`.
        
        The available commands are:
            status [IDENT]
            open IDENT
            close IDENT
            half_open IDENT
            force_open IDENT
            force_closed IDENT

        IDENT identifies a circuit breaker and it's parameter (if such exists), and can
        be found in the first column of the results of calling the 'status' command
        """
        super(SpinningFifoManager, self).__init__(fail_max, reset_timeout,
                exclude, listeners, exception)

        self._input_pipe = input_pipe
        self._output_file = output_file
        self.sleep_delay = sleep_delay
        self.ident_map = {}
        
        self.command_thread = Thread(target=self.io_loop)
        self.command_thread.daemon = True
        self.command_thread.start()

    def io_loop(self):
        """
        Loop forever, checking for a line of input from the input_pipe,
        checking if the line is a command, and executing the command if it is
        """
        if not os.path.exists(self._input_pipe):
            os.mkfifo(self._input_pipe)

        with open(self._input_pipe) as input_pipe:
            while True:
                next_line = input_pipe.readline().strip()

                if next_line == '':
                    sleep(self.sleep_delay)
                    continue

                cmd, _, ident = next_line.partition(' ')

                try:
                    getattr(self, 'do_'+cmd)(ident)
                except AttributeError:
                    log.exception('Invalid command: '+next_line)
                    self.error('Invalid command: '+next_line)
                except InvalidIdentifier as exc:
                    self.error(exc)
                except:
                    log.exception('Unexpected error')
                    self.error('Unexpected error')

    def _compute_id(self, key):
        """
        Returns the IDENT for a particular key from the CircuitBreakerManager.status()
        array. This key uniquely identifies the relevant circuit breaker
        """
        # These indicate a parameterized circuit breaker
        # used with no parameters, so we'll strip off the excess
        # baggage
        if key[1] == None or key[1] == ((), ()):
            return str(key[0])
        else:
            return str(key)

    def status(self):
        """
        Returns the CircuitBreakerManager.status() array, and caches a map from
        of IDENT keys to status() array entries
        """
        status_dict = super(SpinningFifoManager, self).status()
        self.ident_map = dict(
            (self._compute_id(key), key)
            for key in status_dict.keys()
        )
        return status_dict

    def process_ident(self, ident):
        """
        Returns the key in the status() array that is identified by the particular
        IDENT key.

        Raises InvalidIdentifier if no key could be found
        """
        if ident in self.ident_map:
            return self.ident_map[ident]

        # Recompute the identity map
        self.status()

        if ident in self.ident_map:
            return self.ident_map[ident]

        raise InvalidIdentifier(ident)

    def _format_status(self, items):
        """
        Formats the status array into a text table of data. Each column is
        headed by the column name, and separated by 4 spaces ('    ')
        """
        items.sort()
        column_order = ['state', 'time until half_open', 'failure count', 'failures until open']
        lines = [['id'] + column_order]
        for key, status in items:
            lines.append([self._compute_id(key)] + [str(status[col]) for col in column_order])

        cols = zip(*lines)
        col_widths = [max(len(value) for value in col) for col in cols]
        format = '    '.join(['%%%ds' % width for width in col_widths ])

        return '\n'.join(format % tuple(line) for line in lines)

    def do_status(self, ident):
        """
        Execute the status command
        """
        if ident == '':
            self.success(self._format_status(self.status().items()))
        else:
            key = self.process_ident(ident)
            self.success(self._format_status([(key, self.status()[key])]))

    def do_open(self, ident):
        """
        Execute the open command on the circuit breaker specified by IDENT
        """
        self._set_state('open', ident)
    
    def do_half_open(self, ident):
        """
        Execute the half_open command on the circuit breaker specified by IDENT
        """
        self._set_state('half_open', ident)
    
    def do_close(self, ident):
        """
        Execute the close command on the circuit breaker specified by IDENT
        """
        self._set_state('close', ident)

    def do_force_open(self, ident):
        """
        Execute the force_open command on the circuit breaker specified by IDENT
        """
        self._set_state('force_open', ident)

    def do_force_closed(self, ident):
        """
        Execute the force_closed command on the circuit breaker specified by IDENT
        """
        self._set_state('force_closed', ident)

    def _set_state(self, action, ident):
        """
        Execute `action` on the circuit breaker specified by IDENT
        """
        breaker_ident, params = self.process_ident(ident)
        getattr(self, action)(breaker_ident, params)
        self.success("Changed `{ident}` state".format(ident=ident))

    def _output(self, flag, data):
        """
        Write a `flag` and some `data` to the output file
        """
        with open(self._output_file, 'w') as output:
            print >> output, flag
            print >> output, data

    def error(self, line):
        """
        Write the result of a failed command to the output file
        """
        self._output('ERROR', line)

    def success(self, data):
        """
        Write the result of a successful command to the output file
        """
        self._output('SUCCESS', data)


def argparser():
    parser = ArgumentParser()
    parser.add_argument('-i', '--input-path', default=None,
        help='The path that the program is watching for commands. May include the '
             'string "{pid}", which will have the contents of the --pid argument '
             'substituted in. Will override an input_path supplied via the --config '
             'argument.')
    parser.add_argument('-o', '--output-path', default=None,
        help='The path that the program will write responses to. May include the '
             'string "{pid}", which will have the contents of the --pid argument '
             'substituted in. Will override an output_path supplied via the --config '
             'argument.')
    parser.add_argument('-p', '--pid', default=None,
        help='The process id of the process to connect to. Will be substituted in to '
             'the input_path and output_path if they use the "{pid}" string.')
    parser.add_argument('-c', '--config', default=None,
        help='The path to a config file that specifies the input_path and output_path '
             'of the process to connect to.')

    subparsers = parser.add_subparsers()
    status_parser = subparsers.add_parser('status',
        help='Find the status of one or all of the active circuit breakers')
    status_parser.add_argument('ident', nargs='?', default='',
        help='The id string of the circuit breaker to display the status of. If not '
             'given, return the status of all circuit breakers')
    status_parser.set_defaults(cmd_string='status {ident}')

    for command in ['open', 'close', 'half_open', 'force_open', 'force_closed']:
        cmd_parser = subparsers.add_parser(command,
            help='{cmd} the specified circuit breaker'.format(cmd=command))
        cmd_parser.add_argument('ident',
            help='The id string of the circuit breaker to {cmd}'.format(cmd=command))
        cmd_parser.set_defaults(cmd_string='{cmd} {ident}', cmd=command)

    return parser


def command_fifo_manager(input_path, output_path, command, sleep_delay=0.1):
    """
    Execute a `command` against the SpinningFifoManager that uses `input_path` and
    `output_path` to communicate. Wait `sleep_delay` seconds before trying to read `output_path`

    Returns (success, lines), where success is a boolean indicating if the command was
        successful, and lines is an array of the output lines returned by the command
    """
    with open(input_path, 'a') as input_file:
        print >> input_file, command
    
    sleep(sleep_delay)

    with open(output_path) as output_file:
        success = output_file.readline().strip() == 'SUCCESS'
        return success, [line.strip() for line in output_file.readlines()]


def main(args=sys.argv[1:]):
    """
    Main function for a commandline program used to communicate with a SpinningFifoManager
    """
    args = argparser().parse_args()

    input_path = args.input_path
    output_path = args.output_path
    sleep_delay = .1

    if args.config:
        config_parser = SafeConfigParser()
        config_parser.read(args.config_path)
        input_path = config_parser.get('pybreaker', 'input_path', input_path).format(pid=args.pid)
        output_path = config_parser.get('pybreaker', 'output_path', output_path).format(pid=args.pid)
        sleep_delay = float(config_parser.get('pybreaker', 'sleep_delay', sleep_delay))

    if not os.path.exists(input_path):
        print ("No input pipe/file found at {path}. Are you sure you "
               "specified the correct path or config, and the correct pid?")
        return 1

    success, lines = command_fifo_manager(input_path, output_path, args.cmd_string.format(**args.__dict__), sleep_delay)
    print '\n'.join(lines)
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
