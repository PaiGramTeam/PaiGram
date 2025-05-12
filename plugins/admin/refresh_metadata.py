from telegram import Update
from telegram.ext import CallbackContext

from core.dependence.assets.impl.genshin import AssetsService
from core.plugin import Plugin, handler
from metadata.scripts.paimon_moe import update_paimon_moe_zh
from utils.log import logger

__all__ = ("MetadataPlugin",)


class MetadataPlugin(Plugin):
    def __init__(
        self,
        assets_service: AssetsService,
    ):
        self.assets_service = assets_service

    @handler.command("refresh_metadata", admin=True, block=False)
    async def refresh(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 刷新[bold]metadata[/]缓存命令", user.full_name, user.id, extra={"markup": True})

        msg = await message.reply_text("正在刷新元数据，请耐心等待...")
        await update_paimon_moe_zh()
        await self.assets_service.init(True)
        await msg.edit_text("元数据刷新完成！")
