from telegram import Message, User

from core.plugin import Plugin, handler
from metadata.scripts.honey import update_honey_metadata
from metadata.scripts.metadatas import update_metadata_from_ambr, update_metadata_from_github
from metadata.scripts.paimon_moe import update_paimon_moe_zh
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger

__all__ = ("MetadataPlugin",)


class MetadataPlugin(Plugin):
    @bot_admins_rights_check
    @handler.command("refresh_metadata")
    async def refresh(self, user: User, message: Message) -> None:
        logger.info(f"用户 {user.full_name}[{user.id}] 刷新[bold]metadata[/]缓存命令", extra={"markup": True})

        msg = await message.reply_text("正在刷新元数据，请耐心等待...")
        logger.info("正在从 github 上获取元数据")
        await update_metadata_from_github()
        await update_paimon_moe_zh()
        logger.info("正在从 ambr 上获取元数据")
        await update_metadata_from_ambr()
        logger.info("正在从 honey 上获取元数据")
        await update_honey_metadata()
        await msg.edit_text("正在刷新元数据，请耐心等待...\n完成！")
