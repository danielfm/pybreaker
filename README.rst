
PyBreaker
=========

PyBreaker is a Python implementation of the Circuit Breaker pattern, described
in Michael T. Nygard's book `Release It!`_.

In Nygard's words, *"circuit breakers exists to allow one subsystem to fail
without destroying the entire system. This is done by wrapping dangerous
operations (typically integration points) with a component that can circumvent
calls when the system is not healthy"*.


Features
--------

* Configurable list of excluded exceptions (e.g. business exceptions)
* Configurable failure threshold and reset timeout
* Callback functions for state changes and failed/succeeded calls
* Functions and properties for easy monitoring and management
* Thread-safe


Requirements
------------

* `Python`_ 2.6+ (or Python 3.0+)


Installation
------------

Run the following command line to download the latest stable version of
PyBreaker from `PyPI`_::

    $ easy_install -U pybreaker

If you are a `Git`_ user, you might want to download the current development
version::

    $ git clone git://github.com/danielfm/pybreaker.git
    $ cd pybreaker
    $ python setup.py test
    $ python setup.py install


Usage
-----

The first step is to create an instance of ``CircuitBreaker`` for each
integration point::

    import pybreaker
    db_breaker = pybreaker.CircuitBreaker()


To allow better customization while keeping the code self contained, it's
recommended to create subclasses of ``CircuitBreaker`` for each kind of
integration point::

    import pybreaker

    class DBCircuitBreaker(pybreaker.CircuitBreaker):
        def on_state_change(self, old_state, new_state):
            "Called when the circuit breaker state changes."
            pass
        def on_failure(self, exc):
            "Called when a function invocation raises a system error."
            pass
        def on_success(self):
            "Called when a function invocation succeeds."
            pass

    db_breaker = DBCircuitBreaker()


These objects should live globally inside the application scope.


.. note::
  
  Integration points to external services (i.e. databases, queues, etc) are
  more likely to fail, so make sure to always use timeouts when accessing such
  services if there's support at the API level.


Let's say you want to use a circuit breaker on a function that updates a row
in the ``customer`` database table::

    @db_breaker
    def update_customer(cust):
        # Do stuff here...
        pass

    # Will trigger the circuit breaker
    updated_customer = update_customer(my_customer)


Or if you don't want to use the decorator syntax::

    def update_customer(cust):
        # Do stuff here...
        pass

    # Will trigger the circuit breaker
    updated_customer = db_breaker.call(update_customer, my_customer)


What Does a Circuit Breaker Do?
```````````````````````````````

According to the default parameters, the circuit breaker ``db_breaker`` will
automatically open the circuit after 5 consecutive failures in
``update_customer``.

When the circuit is open, all calls to ``update_customer`` will fail immediately
(raising ``CircuitBreakerError``) without any attempt to execute the real
operation.

After 60 seconds, the circuit breaker will allow the next call to
``update_customer`` pass through. If that call succeeds, the circuit is closed;
if it fails, however, the circuit is opened again until another timeout elapses.


Excluding Exceptions
````````````````````

By default, a failed call is any call that raises an exception. However, it's
common to raise exceptions to also indicate business exceptions, and those
exceptions should be ignored by the circuit breaker as they don't indicate
system errors::

    # At creation time
    db_breaker = DBCircuitBreaker(exclude=(CustomerValidationError,))

    # At a later time
    db_breaker.excluded_exceptions += (CustomerValidationError,)


In this case, when any function guarded by that circuit breaker raises
``CustomerValidationError`` (or any exception derived from
``CustomerValidationError``), that call won't be considered a system failure.


Monitoring and Management
`````````````````````````

A ``CircuitBreaker`` object provides properties and functions you can use to
monitor and change its current state::

    # Get the current number of consecutive failures
    print db_breaker.fail_counter

    # Get/set the maximum number of consecutive failures
    print db_breaker.fail_max
    db_breaker.fail_max = 10

    # Get/set the current reset timeout period (in seconds)
    print db_breaker.reset_timeout
    db_breaker.reset_timeout = 60

    # Get the current state, i.e., 'open', 'half-open', 'closed'
    print db_breaker.current_state

    # Closes the circuit
    db_breaker.close()

    # Half-opens the circuit
    db_breaker.half_open()

    # Opens the circuit
    db_breaker.open()


These properties and functions might and should be exposed to the operations
staff as they help them find problems in the system.


.. _Python: http://python.org
.. _Jython: http://jython.org
.. _Release It!: http://pragprog.com/titles/mnee/release-it
.. _PyPI: http://pypi.python.org
.. _Git: http://git-scm.com
