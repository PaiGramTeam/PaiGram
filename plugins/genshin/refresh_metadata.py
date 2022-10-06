from telegram import Update

from core.plugin import Plugin, handler
from metadata.scripts.honey import update_honey_metadata
from metadata.scripts.metadata import update_metadata_from_ambr, update_metadata_from_github
from utils.decorators.admins import bot_admins_rights_check
from utils.log import logger


class MetadataPlugin(Plugin):

    @handler.command('refresh_metadata')
    @bot_admins_rights_check
    async def refresh(self, update: Update, _) -> None:
        user = update.effective_user
        message = update.effective_message

        logger.info(
            f"用户 {user.full_name}[{user.id}] 刷新[bold]metadata[/]缓存命令", extra={'markup': True}
        )

        msg = await message.reply_text("正在刷新元数据，请耐心等待...")
        logger.info("正在从 github 上获取元数据")
        await update_metadata_from_github()
        logger.info("正在从 ambr 上获取元数据")
        await update_metadata_from_ambr()
        logger.info("正在从 honey 上获取元数据")
        await update_honey_metadata()
        await msg.edit_text("正在刷新元数据，请耐心等待...\n完成！")
