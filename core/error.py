"""此模块包含核心模块的错误的基类"""


class ServiceNotFoundError(Exception):

    def __init__(self, name):
        super().__init__(f"No service named '{name}'")
