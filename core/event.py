from typing import Generic, Tuple, TypeVar, Union

from telegram import Update
from telegram.ext import CallbackContext

from utils.enums import Priority

__all__ = ['Event']

T = TypeVar('T')


class Event(Generic[T]):
    type: str
    data: T
    priority: Union[Priority, int]

    def __init__(self, event_type: str, data: T, priority: Priority = Priority.Normal) -> None:
        self.type = event_type
        self.data = data
        self.priority = priority


class TelegramEvent(Event[Tuple[Update, CallbackContext]]):
    pass
