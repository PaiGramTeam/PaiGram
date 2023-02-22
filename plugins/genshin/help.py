from telegram import Bot, Message, User
from telegram.constants import ChatAction

from core.plugin import Plugin, handler
from core.services.template import TemplateService
from utils.decorators.restricts import restricts
from utils.log import logger

__all__ = ("HelpPlugin",)


class HelpPlugin(Plugin):
    def __init__(self, template_service: TemplateService = None):
        if template_service is None:
            raise ModuleNotFoundError
        self.template_service = template_service

    @restricts()
    @handler.command(command="help", block=False)
    async def start(self, user: User, message: Message, bot: Bot):
        logger.info("用户 %s[%s] 发出help命令", user.full_name, user.id)
        await message.reply_chat_action(ChatAction.TYPING)
        render_result = await self.template_service.render(
            "bot/help/help.html",
            {"bot_username": bot.username},
            {"width": 1280, "height": 900},
            ttl=30 * 24 * 60 * 60,
        )
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename="help.png", allow_sending_without_reply=True)
