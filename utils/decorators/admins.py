from typing import Callable

from telegram import Update

from utils.base import PaimonContext


def bot_admins_rights_check(func: Callable) -> Callable:
    async def decorator(self, update: Update, context: PaimonContext):
        service = context.service
        admin_list = await service.admin.get_admin_list()
        if update.message.from_user.id in admin_list:
            return await func(self, update, context)
        else:
            await update.message.reply_text("权限不足")
            return None

    return decorator
