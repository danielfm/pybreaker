from pybreaker import CircuitBreaker

# issue #90: incorrect typing for exclude argument
# this should not give errors in mypy
CircuitBreaker(
    fail_max=1,
    reset_timeout=1000,
    exclude=[lambda e: isinstance(e, RuntimeError)],
)
