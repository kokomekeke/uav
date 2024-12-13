import time


def run_once(timeout: float = 0):
    """
    Decorator for making a function only run once.
    If timeout is specified, the function will be excecuted on the next call if the
    timeout has elapsed since the last excecution.

    For being able to call a function both with and without this decorator do this:
        >>> my_func_run_once = run_once(timeout=1)(my_func)

    TODO: add tests
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            current_time = time.time()
            if (
                not wrapper.last_run_time
                or current_time - wrapper.last_run_time > timeout > 0
            ):
                # run if it never ran before, or a timeout has been set and exceeded
                wrapper.last_run_time = current_time
                return func(*args, **kwargs)

        wrapper.last_run_time = 0
        return wrapper

    return decorator
