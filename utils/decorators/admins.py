from functools import wraps
from typing import Callable

from core.builtins.contexts import BotContext, TGUpdate
from core.error import ServiceNotFoundError
from core.services.users.services import UserAdminService

__all__ = ("bot_admins_rights_check",)


def bot_admins_rights_check(func: Callable) -> Callable:
    """BOT ADMIN 权限检查"""

    @wraps(func)
    async def decorator(*args, **kwargs):
        update = TGUpdate.get()
        bot = BotContext.get()

        service: UserAdminService = bot.services_map.get(UserAdminService, None)

        if service is None:
            raise ServiceNotFoundError("BotAdminService")

        message = update.effective_message
        user = update.effective_user

        if await service.is_admin(user.id):
            return await func(*args, **kwargs)
        else:
            await message.reply_text("权限不足")
        return None

    return decorator
