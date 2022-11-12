from typing import Optional

from telegram import Update, ReplyKeyboardRemove, Message, User, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler
from telegram.helpers import escape_markdown

from core.base.redisdb import RedisDB
from core.config import config
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import handler, Plugin
from core.user import UserService
from core.user.error import UserNotFoundError
from modules.apihelper.hyperion import Verification
from plugins.genshin.sign import SignSystem, NeedChallenge
from plugins.genshin.verification import VerificationSystem
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger
from utils.models.base import RegionEnum


class StartPlugin(Plugin):
    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None, redis: RedisDB = None):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_system = SignSystem(redis)
        self.verification_system = VerificationSystem(redis)

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
                await self.process_validate(message, user, bot_username=context.bot.username)
            elif args[0] == "sign":
                await self.gen_sign_button(message, user)
            elif args[0].startswith("challenge_"):
                _data = args[0].split("_")
                _command = _data[1]
                _challenge = _data[2]
                if _command == "sign":
                    await self.process_sign_validate(message, user, _challenge)
                elif _command == "verify":
                    await self.process_validate(message, user, validate=_challenge)
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
            button = await self.sign_system.get_challenge_button(client.uid, user.id, callback=False)
            if not button:
                await message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            await message.reply_text("请尽快点击下方按钮进行验证。", allow_sending_without_reply=True, reply_markup=button)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.warning("用户 %s[%s] 账号信息未找到", user.full_name, user.id)

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
            logger.warning("用户 %s[%s] 账号信息未找到", user.full_name, user.id)
        except NeedChallenge:
            await message.reply_text("回调错误，请重新签到", allow_sending_without_reply=True)

    async def process_validate(
        self, message: Message, user: User, validate: Optional[str] = None, bot_username: Optional[str] = None
    ):
        user_info = await self.user_service.get_user_by_id(user.id)
        if user_info.region != RegionEnum.HYPERION:
            await message.reply_text("非法用户")
            return
        uid = user_info.yuanshen_uid
        cookie = await self.cookies_service.get_cookies(user.id, RegionEnum.HYPERION)
        client = Verification(cookie=cookie.cookies)
        if validate:
            _, challenge = await self.verification_system.get_challenge(uid)
            if challenge:
                await client.verify(challenge, validate)
                await message.reply_text("验证成功")
            else:
                await message.reply_text("验证失效")
        if bot_username:
            data = await client.create()
            challenge = data["challenge"]
            gt = data["gt"]
            validate = await client.ajax(referer="https://webstatic.mihoyo.com/", gt=gt, challenge=challenge)
            if validate:
                await client.verify(challenge, validate)
                await message.reply_text("验证成功")
                return
            await self.sign_system.set_challenge(uid, gt, challenge)
            url = f"{config.pass_challenge_user_web}?username={bot_username}&command=verify&gt={gt}&challenge={challenge}&uid={uid}"
            button = InlineKeyboardMarkup([[InlineKeyboardButton("验证", url=url)]])
            await message.reply_text("请尽快点击下方手动验证", reply_markup=button)
