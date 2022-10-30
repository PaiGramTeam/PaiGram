import contextlib

from telegram import Update, ReplyKeyboardRemove
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler
from telegram.helpers import escape_markdown

from core.cookies.error import CookiesNotFoundError
from core.plugin import handler, Plugin
from core.user.error import UserNotFoundError
from plugins.genshin.sign import Sign
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client


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
            elif args[0].startswith("challenge_"):
                await StartPlugin.process_sign_validate(update, args[0][10:])
            else:
                await message.reply_html(f"你好 {user.mention_html()} ！我是派蒙 ！\n请点击 /{args[0]} 命令进入对应流程")
            return
        await message.reply_markdown_v2(f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}")

    @staticmethod
    async def process_sign_validate(update: Update, validate: str):
        with contextlib.suppress(UserNotFoundError, CookiesNotFoundError):
            client = await get_genshin_client(update.effective_user.id)
            await update.effective_message.reply_chat_action(ChatAction.TYPING)
            headers = await Sign.gen_challenge_header(update.effective_user.id, validate)
            if not headers:
                await update.effective_message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            sign_text, button = await Sign.start_sign(client, headers)
            await update.effective_message.reply_text(sign_text, allow_sending_without_reply=True, reply_markup=button)

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
