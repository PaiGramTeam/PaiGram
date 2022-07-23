import inspect
from functools import wraps

from logger import Log
from model.types import Func
from utils.app.manager import ServiceDict


def inject(func: Func) -> Func:
    """依赖注入"""
    @wraps(func)
    async def decorator(*args, **kwargs):
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
                class_name = annotation.__class__.__name__
                param = ServiceDict.get(class_name)
                kwargs.setdefault(class_name, param)

        return await func(*args, **kwargs)

    return decorator
