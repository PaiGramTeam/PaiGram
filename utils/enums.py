from enum import IntEnum

__all__ = ("Priority",)


class Priority(IntEnum):
    """优先级"""

    Lowest = 0
    Low = 4
    Normal = 8
    High = 12
    Highest = 16
