import time
from functools import wraps
from typing import Callable

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import filters, CallbackContext

from logger import Log


def restricts(filters_chat: filters = filters.ALL, return_data=None, try_delete_message: bool = False,
              restricts_time: int = 5):
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

    我真™是服了某些闲着没事干的群友了

    :param filters_chat: 要限制的群
    :param return_data:
    :param try_delete_message:
    :param restricts_time:
    :return: return_data
    """

    def decorator(func: Callable):
        @wraps(func)
        async def restricts_func(*args, **kwargs):
            if len(args) == 3:
                update: Update = args[1]
                context: CallbackContext = args[2]
            elif len(args) == 2:
                update: Update = args[0]
                context: CallbackContext = args[1]
            else:
                return await func(*args, **kwargs)
            message = update.message
            user = update.effective_user
            if filters_chat.filter(message):
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
                        await update.effective_message.reply_text("你已经触发洪水防御，请等待5分钟")
                        Log.warning(f"用户 {user.full_name}[{user.id}] 触发洪水限制 已被限制5分钟")
                        return return_data
                # 单次使用限制
                if command_time:
                    if (time.time() - command_time) <= restricts_time:
                        context.user_data["usage_count"] = count + 1
                        if filters.ChatType.GROUPS.filter(message):
                            if try_delete_message:
                                try:
                                    await message.delete()
                                except TelegramError as error:
                                    Log.warning("删除消息失败", error)
                            return return_data
                    else:
                        if count >= 1:
                            context.user_data["usage_count"] = count - 1

                context.user_data["command_time"] = time.time()

            return await func(*args, **kwargs)

        return restricts_func

    return decorator
