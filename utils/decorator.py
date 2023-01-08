from contextlib import contextmanager

__all__ = ["do_nothing"]


@contextmanager
def do_nothing():
    try:
        yield
    finally:
        ...
