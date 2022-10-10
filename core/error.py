"""此模块包含核心模块的错误的基类"""
from typing import Union


class ServiceNotFoundError(Exception):
    def __init__(self, name: Union[str, type]):
        super().__init__(f"No service named '{name if isinstance(name, str) else name.__name__}'")
