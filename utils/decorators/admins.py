from functools import wraps
from typing import Callable

from apps.admin.services import BotAdminService
from utils.service.inject import inject


def bot_admins_rights_check(func: Callable) -> Callable:
    """BOT ADMIN 权限检查"""

    @inject
    def get_bot_admin_service(bot_admin_service: BotAdminService = None):
        return bot_admin_service

    @wraps(func)
    async def decorator(*args, **kwargs):
        if len(args) == 3:
            # self update context
            _, update, context = args
        elif len(args) == 2:
            # update context
            update, context = args
        else:
            return await func(*args, **kwargs)
        bot_admin_service = get_bot_admin_service()
        if bot_admin_service is None:
            raise RuntimeError("bot_admin_service is None")
        admin_list = await bot_admin_service.get_admin_list()
        if update.message.from_user.id in admin_list:
            return await func(*args, **kwargs)
        else:
            await update.message.reply_text("权限不足")
        return None

    return decorator
