import asyncio
import time
from functools import wraps
from typing import Callable, Optional, TYPE_CHECKING, TypeVar, Union

from telegram.ext import filters
from typing_extensions import ParamSpec

from core.builtins.contexts import TGContext, TGUpdate
from utils.const import WRAPPER_ASSIGNMENTS
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import CallbackContext
    from telegram import Update

__all__ = ("restricts",)

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")

_lock = asyncio.Lock()


def restricts(
    restricts_time: int = 9,
    restricts_time_of_groups: Optional[int] = None,
    return_data: T = None,
    without_overlapping: bool = False,
):
    """用于装饰在指定函数预防洪水攻击的装饰器
    如果修饰的函数属于 `telegram.ext.ConversationHandler`,
    则参数 `return_data` 必须传入 `telegram.ext.ConversationHandler.END`

    **我真™是服了某些闲着没事干的群友了**

    Args:
        restricts_time (int): 基础限制时间，单位为秒，默认为 9
        restricts_time_of_groups (int | None): 对群限制的时间，单位为秒，默认为 None
        return_data (Any):
            返回的数据, 对于 `telegram.ext.ConversationHandler` 需要传入
            `telegram.ext.ConversationHandler.END` , 默认为 None
        without_overlapping (bool): 两次命令时间不覆盖，在上一条一样的命令返回之前，忽略重复调用, 默认为 False

    Returns:
        被装饰后的函数
    """

    def decorator(func: Callable[P, R]) -> Callable[P, Union[R, T]]:
        @wraps(func, assigned=WRAPPER_ASSIGNMENTS)
        async def restricts_func(*args: P.args, **kwargs: P.kwargs) -> Union[R, T]:
            update: "Update" = TGUpdate.get()
            context: "CallbackContext" = TGContext.get()

            message = update.effective_message
            user = update.effective_user

            _restricts_time = restricts_time
            if restricts_time_of_groups is not None and filters.ChatType.GROUPS.filter(message):
                _restricts_time = restricts_time_of_groups

            async with _lock:
                user_lock = context.user_data.get("lock")
                if user_lock is None:
                    user_lock = context.user_data["lock"] = asyncio.Lock()

            # 如果上一个命令还未完成，忽略后续重复调用
            if without_overlapping and user_lock.locked():
                logger.warning("用户 %s[%s] 触发 overlapping 该次命令已忽略", user.full_name, user.id)
                return return_data

            async with user_lock:
                command_time = context.user_data.get("command_time", 0)
                count = context.user_data.get("usage_count", 0)
                restrict_since = context.user_data.get("restrict_since", 0)

                # 洪水防御
                if restrict_since:
                    if (time.time() - restrict_since) >= 60:
                        del context.user_data["restrict_since"]
                        del context.user_data["usage_count"]
                    else:
                        return return_data
                else:
                    if count >= 6:
                        context.user_data["restrict_since"] = time.time()
                        if update.callback_query:
                            await update.callback_query.answer("你已经触发洪水防御，请等待60秒", show_alert=True)
                        else:
                            await message.reply_text("你已经触发洪水防御，请等待60秒")
                        logger.warning("用户 %s[%s] 触发洪水限制 已被限制60秒", user.full_name, user.id)
                        return return_data
                # 单次使用限制
                if command_time:
                    if (time.time() - command_time) <= _restricts_time:
                        context.user_data["usage_count"] = count + 1
                    else:
                        if count >= 1:
                            context.user_data["usage_count"] = count - 1
                context.user_data["command_time"] = time.time()

                # 只需要给 without_overlapping 的代码加锁运行
                if without_overlapping:
                    return await func(*args, **kwargs)

            if count > 1:
                await asyncio.sleep(count)
            return await func(*args, **kwargs)

        return restricts_func

    return decorator
