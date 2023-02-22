"""上下文管理"""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram.ext import CallbackContext
    from telegram import Update

__all__ = [
    "TGContext",
    "TGUpdate",
    "handler_contexts",
    "job_contexts",
]

TGContext: ContextVar["CallbackContext"] = ContextVar("TGContext")
TGUpdate: ContextVar["Update"] = ContextVar("TGUpdate")


@contextmanager
def handler_contexts(update: "Update", context: "CallbackContext") -> None:
    context_token = TGContext.set(context)
    update_token = TGUpdate.set(update)
    try:
        yield
    finally:
        TGContext.reset(context_token)
        TGUpdate.reset(update_token)


@contextmanager
def job_contexts(context: "CallbackContext") -> None:
    token = TGContext.set(context)
    try:
        yield
    finally:
        TGContext.reset(token)
