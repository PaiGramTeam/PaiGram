import inspect
from functools import wraps

from logger import Log
from models.types import Func
from utils.service.manager import ServiceDict


def get_injections(func: Func):
    injections = {}
    try:
        signature = inspect.signature(func)
    except ValueError as exception:
        if "no signature found" in str(exception):
            Log.warning("no signature found", exception)
        elif "not supported by signature" in str(exception):
            Log.warning("not supported by signature", exception)
        else:
            raise exception
    else:
        for parameter_name, parameter in signature.parameters.items():
            annotation = parameter.annotation
            class_name = annotation.__name__
            param = ServiceDict.get(class_name)
            if param is not None:
                injections.setdefault(parameter_name, param)
    return injections


def inject(func: Func) -> Func:
    """依赖注入"""

    @wraps(func)
    async def async_decorator(*args, **kwargs):
        injections = get_injections(func)
        kwargs.update(injections)
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_decorator(*args, **kwargs):
        injections = get_injections(func)
        kwargs.update(injections)
        return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_decorator
    else:
        return sync_decorator
