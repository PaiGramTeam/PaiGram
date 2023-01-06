from functools import wraps
from typing import Callable, cast

from telegram import Update

from core.bot import bot
from core.error import ServiceNotFoundError
from core.services.admin import BotAdminService

bot_admin_service = bot.services.get(BotAdminService)


def bot_admins_rights_check(func: Callable) -> Callable:
    """BOT ADMIN 权限检查"""

    @wraps(func)
    async def decorator(*args, **kwargs):
        if len(args) == 3:
            # self update context
            _, update, _ = args
        elif len(args) == 2:
            # update context
            update, _ = args
        else:
            return await func(*args, **kwargs)
        if bot_admin_service is None:
            raise ServiceNotFoundError("BotAdminService")
        admin_list = await bot_admin_service.get_admin_list()
        update = cast(Update, update)
        message = update.effective_message
        user = update.effective_user
        if user.id in admin_list:
            return await func(*args, **kwargs)
        else:
            await message.reply_text("权限不足")
        return None

    return decorator
