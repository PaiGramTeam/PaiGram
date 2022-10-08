from telegram import Update
from telegram.ext import CallbackContext, CommandHandler

from core.plugin import handler, Plugin
from utils.bot import get_all_args
from utils.decorators.admins import bot_admins_rights_check
from utils.helpers import execute
from utils.log import logger


class UpdatePlugin(Plugin):

    @handler(CommandHandler, command="update", block=False)
    @bot_admins_rights_check
    async def update(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        args = get_all_args(context)
        logger.info(f"用户 {user.full_name}[{user.id}] update命令请求")
        reply_text = await message.reply_text("正在更新")
        await execute("git fetch --all")
        if len(args) > 0:
            await execute("git reset --hard origin/master")
        await execute("git pull --all")
        if len(args) > 0:
            await execute("poetry install --extras all")
        await reply_text.edit_text("自动更新成功 正在重启")
        raise SystemExit
