import asyncio
import contextlib
from typing import Callable, Coroutine, Any, Union, List, Dict, Optional, TypeVar, Type, TYPE_CHECKING

from telegram.error import RetryAfter
from telegram.ext import BaseRateLimiter, ApplicationHandlerStop

from utils.log import logger

JSONDict: Type[dict[str, Any]] = Dict[str, Any]
RL_ARGS = TypeVar("RL_ARGS")


class RateLimiter(BaseRateLimiter[int]):
    __slots__ = (
        "_limiter_info",
        "_retry_after_event",
    )

    def __init__(self):
        self._limiter_info: Dict[Union[str, int], float] = {}
        self._retry_after_event = asyncio.Event()
        self._retry_after_event.set()

    async def process_request(
        self,
        callback: Callable[..., Coroutine[Any, Any, Union[bool, JSONDict, List[JSONDict]]]],
        args: Any,
        kwargs: Dict[str, Any],
        endpoint: str,
        data: Dict[str, Any],
        rate_limit_args: Optional[RL_ARGS],
    ) -> Union[bool, JSONDict, List[JSONDict]]:
        chat_id = data.get("chat_id")

        with contextlib.suppress(ValueError, TypeError):
            chat_id = int(chat_id)

        loop = asyncio.get_running_loop()
        time = loop.time()
        chat_limit_time = self._limiter_info.get(chat_id)
        if chat_limit_time:
            if time >= chat_limit_time:
                raise ApplicationHandlerStop
            else:
                del self._limiter_info[chat_id]
        await self._retry_after_event.wait()
        try:
            return await callback(*args, **kwargs)
        except RetryAfter as exc:
            logger.warning("触发洪水限制\nchat_id=%s, retry_after=%s", chat_id, exc.retry_after)
            self._limiter_info[chat_id] = time + (exc.retry_after * 2)
            sleep = exc.retry_after + 0.1
            self._retry_after_event.clear()
            await asyncio.sleep(sleep)
        finally:
            self._retry_after_event.set()

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
