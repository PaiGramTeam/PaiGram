import asyncio
import time
from functools import wraps
from typing import Callable, cast, Optional, Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import filters, CallbackContext

from utils.log import logger

_lock = asyncio.Lock()


def restricts(restricts_time: int = 5, restricts_time_of_groups: Optional[int] = None, return_data: Any = None,
              try_delete_message: bool = False, without_overlapping: bool = False):
    """用于装饰在指定函数预防洪水攻击的装饰器

    被修饰的函数生声明必须为

    async def command_func(update, context)
    或
    async def command_func(self, update, context

    如果修饰的函数属于
    ConversationHandler
    参数
    return_data
    必须传入
    ConversationHandler.END

    如果在一个 handler 上添加多个 restricts 修饰器，只能在第一个修饰器打开
    without_overlapping，否则两次修饰器会认为重复了，完全忽略调用。

    我真™是服了某些闲着没事干的群友了

    :param restricts_time: 基础限制时间
    :param restricts_time_of_groups: 对群限制的时间
    :param return_data: 返回的数据对于 ConversationHandler 需要传入 ConversationHandler.END
    :param try_delete_message: 触发洪水后是否尝试删除消息
    :param without_overlapping: 两次命令时间不覆盖，在上一条一样的命令返回之前，忽略重复调用
    """

    def decorator(func: Callable):
        @wraps(func)
        async def restricts_func(*args, **kwargs):
            if len(args) == 3:
                # self update context
                _, update, context = args
            elif len(args) == 2:
                # update context
                update, context = args
            else:
                return await func(*args, **kwargs)
            update = cast(Update, update)
            context = cast(CallbackContext, context)
            message = update.effective_message
            user = update.effective_user

            _restricts_time = restricts_time
            if restricts_time_of_groups is not None:
                if filters.ChatType.GROUPS.filter(message):
                    _restricts_time = restricts_time_of_groups

            async with _lock:
                user_lock = context.user_data.get("lock")
                if user_lock is None:
                    user_lock = context.user_data["lock"] = asyncio.Lock()

            # 如果上一个命令还未完成，忽略后续重复调用
            if without_overlapping and user_lock.locked():
                logger.warning(f"用户 {user.full_name}[{user.id}] 触发 overlapping 该次命令已忽略")
                return return_data

            async with user_lock:
                command_time = context.user_data.get("command_time", 0)
                count = context.user_data.get("usage_count", 0)
                restrict_since = context.user_data.get("restrict_since", 0)

                # 洪水防御
                if restrict_since:
                    if (time.time() - restrict_since) >= 60 * 5:
                        del context.user_data["restrict_since"]
                        del context.user_data["usage_count"]
                    else:
                        return return_data
                else:
                    if count == 5:
                        context.user_data["restrict_since"] = time.time()
                        await message.reply_text("你已经触发洪水防御，请等待5分钟")
                        logger.warning(f"用户 {user.full_name}[{user.id}] 触发洪水限制 已被限制5分钟")
                        return return_data
                # 单次使用限制
                if command_time:
                    if (time.time() - command_time) <= _restricts_time:
                        context.user_data["usage_count"] = count + 1
                        if try_delete_message:
                            if filters.ChatType.GROUPS.filter(message):
                                try:
                                    await message.delete()
                                except TelegramError as exc:
                                    logger.warning("删除消息失败")
                                    logger.exception(exc)
                            return return_data
                    else:
                        if count >= 1:
                            context.user_data["usage_count"] = count - 1
                context.user_data["command_time"] = time.time()

                # 只需要给 without_overlapping 的代码加锁运行
                if without_overlapping:
                    return await func(*args, **kwargs)

            return await func(*args, **kwargs)

        return restricts_func

    return decorator
