from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext, CommandHandler
from telegram.helpers import escape_markdown

from core.plugin import handler, Plugin
from utils.log import logger


class StartPlugin(Plugin):
    @handler.command("start", block=False)
    async def start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = context.args
        args_text = " ".join(args) if args else ""
        logger.info("用户 %s[%s] 发出start命令 args[%s]", user.full_name, user.id, args_text)
        if args is not None and len(args) >= 1:
            return
        await message.reply_markdown_v2(f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}")

    @staticmethod
    async def unknown_command(update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("前面的区域，以后再来探索吧！")

    @staticmethod
    async def emergency_food(update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("派蒙才不是应急食品！")

    @handler(CommandHandler, command="ping", block=False)
    async def ping(self, update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("online! ヾ(✿ﾟ▽ﾟ)ノ")

    @handler(CommandHandler, command="reply_keyboard_remove", block=False)
    async def reply_keyboard_remove(self, update: Update, _: CallbackContext) -> None:
        await update.message.reply_text("移除远程键盘成功", reply_markup=ReplyKeyboardRemove())
