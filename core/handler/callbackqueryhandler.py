import asyncio
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import TypeVar, TYPE_CHECKING, Any, Optional, Type

from telegram.ext import CallbackQueryHandler as BaseCallbackQueryHandler, ApplicationHandlerStop

from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import Application

RT = TypeVar("RT")
UT = TypeVar("UT")
CCT = TypeVar("CCT", bound="CallbackContext[Any, Any, Any, Any]")


class OverlappingException(Exception):
    pass


class OverlappingContext(AbstractAsyncContextManager):
    _lock = asyncio.Lock()

    def __init__(self, context: "CCT"):
        self.context = context

    async def __aenter__(self) -> None:
        async with self._lock:
            flag = self.context.user_data.get("overlapping", False)
            if flag:
                raise OverlappingException
            self.context.user_data["overlapping"] = True
            return None

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        async with self._lock:
            del self.context.user_data["overlapping"]
            return None


class CallbackQueryHandler(BaseCallbackQueryHandler):
    async def handle_update(
        self,
        update: "UT",
        application: "Application[Any, CCT, Any, Any, Any, Any]",
        check_result: Any,
        context: "CCT",
    ) -> RT:
        self.collect_additional_context(context, update, application, check_result)
        try:
            async with OverlappingContext(context):
                return await self.callback(update, context)
        except OverlappingException as exc:
            user = update.effective_user
            logger.warning("用户 %s[%s] 触发 overlapping 该次命令已忽略", user.full_name, user.id)
            raise ApplicationHandlerStop from exc
