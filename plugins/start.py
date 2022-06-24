from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown

from utils.base import PaimonContext
from plugins.base import restricts


@restricts()
async def start(update: Update, context: PaimonContext) -> None:
    user = update.effective_user
    message = update.message
    args = context.args
    if args is not None:
        if len(args) >= 1:
            if args[1] == "inline_message":
                await message.reply_markdown_v2(f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                                                f"{escape_markdown('发送 /help 命令即可查看命令帮助')}")
                return
    await update.message.reply_markdown_v2(f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}")


@restricts()
async def help_command(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text("前面的区域，以后再来探索吧！")


@restricts()
async def unknown_command(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text("前面的区域，以后再来探索吧！")


@restricts()
async def emergency_food(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text("派蒙才不是应急食品！")


@restricts()
async def ping(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text("online! ヾ(✿ﾟ▽ﾟ)ノ")


@restricts()
async def reply_keyboard_remove(update: Update, _: CallbackContext) -> None:
    await update.message.reply_text("移除远程键盘成功", reply_markup=ReplyKeyboardRemove())
