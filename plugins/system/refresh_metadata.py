from telegram import Message, User

from core.plugin import Plugin, handler
from metadata.scripts.honey import update_honey_metadata
from metadata.scripts.metadatas import update_metadata_from_ambr, update_metadata_from_github
from metadata.scripts.paimon_moe import update_paimon_moe_zh

from utils.log import logger

__all__ = ("MetadataPlugin",)


class MetadataPlugin(Plugin):
    @handler.command("refresh_metadata", admin=True)
    async def refresh(self, user: User, message: Message) -> None:
        logger.info("用户 %s[%s] 刷新[bold]metadata[/]缓存命令", user.full_name, user.id, extra={"markup": True})

        msg = await message.reply_text("正在刷新元数据，请耐心等待...")
        logger.info("正在从 github 上获取元数据")
        await update_metadata_from_github()
        await update_paimon_moe_zh()
        logger.info("正在从 ambr 上获取元数据")
        await update_metadata_from_ambr()
        logger.info("正在从 honey 上获取元数据")
        await update_honey_metadata()
        await msg.edit_text("正在刷新元数据，请耐心等待...\n完成！")
