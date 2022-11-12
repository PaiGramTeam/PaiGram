from telegram import Update, ReplyKeyboardRemove, Message, User
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler
from telegram.helpers import escape_markdown

from core.base.redisdb import RedisDB
from core.cookies.error import CookiesNotFoundError
from core.plugin import handler, Plugin
from core.user.error import UserNotFoundError
from plugins.genshin.sign import SignSystem, NeedChallenge
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class StartPlugin(Plugin):
    def __init__(self, redis: RedisDB = None):
        self.sign_system = SignSystem(redis)

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
            elif args[0] == "verify_verification":
                await message.reply_markdown_v2(
                    f"你好 {user.mention_markdown_v2()} {escape_markdown('！我是派蒙 ！')}\n"
                    f"{escape_markdown('发送 /verif 命令进入认证流程')}"
                )
            elif args[0] == "sign":
                await self.gen_sign_button(message, user)
            elif args[0].startswith("challenge_"):
                await self.process_sign_validate(message, user, args[0][10:])
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

    async def gen_sign_button(self, message: Message, user: User):
        try:
            client = await get_genshin_client(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            button = await self.sign_system.gen_challenge_button(client.uid, user.id)
            if not button:
                await message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            await message.reply_text("请尽快点击下方按钮进行验证。", allow_sending_without_reply=True, reply_markup=button)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.warning(f"用户 {user.full_name}[{user.id}] 账号信息未找到")

    async def process_sign_validate(self, message: Message, user: User, validate: str):
        try:
            client = await get_genshin_client(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            headers = await self.sign_system.gen_challenge_header(client.uid, validate)
            if not headers:
                await message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            sign_text = await self.sign_system.start_sign(client, headers=headers)
            await message.reply_text(sign_text, allow_sending_without_reply=True)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.warning(f"用户 {user.full_name}[{user.id}] 账号信息未找到")
        except NeedChallenge:
            await message.reply_text("回调错误，请重新签到", allow_sending_without_reply=True)
