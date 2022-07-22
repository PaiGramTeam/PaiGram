from typing import Dict, Any, Callable, TypeVar

JSONDict = Dict[str, Any]

Func = TypeVar("Func", bound=Callable[..., Any])
