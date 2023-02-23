"""上下文管理"""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram.ext import CallbackContext
    from telegram import Update

__all__ = [
    "CallbackContextCV",
    "UpdateCV",
    "handler_contexts",
    "job_contexts",
]

CallbackContextCV: ContextVar["CallbackContext"] = ContextVar("TelegramContextCallback")
UpdateCV: ContextVar["Update"] = ContextVar("TelegramUpdate")


@contextmanager
def handler_contexts(update: "Update", context: "CallbackContext") -> None:
    context_token = CallbackContextCV.set(context)
    update_token = UpdateCV.set(update)
    try:
        yield
    finally:
        CallbackContextCV.reset(context_token)
        UpdateCV.reset(update_token)


@contextmanager
def job_contexts(context: "CallbackContext") -> None:
    token = CallbackContextCV.set(context)
    try:
        yield
    finally:
        CallbackContextCV.reset(token)
