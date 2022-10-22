from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext, CommandHandler
from telegram.helpers import escape_markdown

from core.plugin import handler, Plugin
from utils.decorators.restricts import restricts


class StartPlugin(Plugin):
    @handler(CommandHandler, command="start", block=False)
    @restricts()
    async def start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = context.args
        if args is not None and len(args) >= 1:
            if args[0] == "inline_message":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /help 命令即可查看命令帮助')}"
                )
            elif args[0] == "set_cookie":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /setcookie 命令进入绑定账号流程')}"
                )
            elif args[0] == "set_uid":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /setuid 或 /setcookie 命令进入绑定账号流程')}"
                )
            else:
                await message.reply_html(f"你好 {user.mention_html()} ！我是派蒙 ！\n请点击 /{args[0]} 命令进入对应流程")
            return
        await message.reply_markdown_v2(f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}")

    @staticmethod
    @restricts()
    async def unknown_command(update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("前面的区域，以后再来探索吧！")

    @staticmethod
    @restricts()
    async def emergency_food(update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("派蒙才不是应急食品！")

    @handler(CommandHandler, command="ping", block=False)
    @restricts()
    async def ping(self, update: Update, _: CallbackContext) -> None:
        await update.effective_message.reply_text("online! ヾ(✿ﾟ▽ﾟ)ノ")

    @handler(CommandHandler, command="reply_keyboard_remove", block=False)
    @restricts()
    async def reply_keyboard_remove(self, update: Update, _: CallbackContext) -> None:
        await update.message.reply_text("移除远程键盘成功", reply_markup=ReplyKeyboardRemove())
