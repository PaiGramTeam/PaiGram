from typing import Optional

from genshin import Region, GenshinException
from telegram import Update, ReplyKeyboardRemove, Message, User, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
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
from modules.apihelper.error import ResponseException, APIHelperException
from modules.apihelper.hyperion import Verification
from plugins.genshin.sign import SignSystem, NeedChallenge
from plugins.genshin.verification import VerificationSystem
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class StartPlugin(Plugin):
    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None, redis: RedisDB = None):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_system = SignSystem(redis)
        self.verification_system = VerificationSystem(redis)

    @handler.command("start", block=False)
    @error_callable
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
                logger.info(f"用户 %s[%s] 通过start命令 获取认证信息", user.full_name, user.id)
                await self.process_validate(message, user, bot_username=context.bot.username)
            elif args[0] == "sign":
                logger.info(f"用户 %s[%s] 通过start命令 获取签到信息", user.full_name, user.id)
                await self.gen_sign_button(message, user)
            elif args[0].startswith("challenge_"):
                _data = args[0].split("_")
                _command = _data[1]
                _challenge = _data[2]
                if _command == "sign":
                    logger.info(f"用户 %s[%s] 通过start命令 进入签到流程", user.full_name, user.id)
                    await self.process_sign_validate(message, user, _challenge)
            else:
                await message.reply_html(f"你好 {user.mention_html()} ！我是派蒙 ！\n请点击 /{args[0]} 命令进入对应流程")
            return
        logger.info(f"用户 %s[%s] 发出start命令", user.full_name, user.id)
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
            _, challenge = await self.sign_system.get_challenge(client.uid)
            if not challenge:
                await message.reply_text("验证请求已过期。", allow_sending_without_reply=True)
                return
            sign_text = await self.sign_system.start_sign(client, challenge=challenge, validate=validate)
            await message.reply_text(sign_text, allow_sending_without_reply=True)
        except (UserNotFoundError, CookiesNotFoundError):
            logger.warning("用户 %s[%s] 账号信息未找到", user.full_name, user.id)
        except NeedChallenge:
            await message.reply_text("回调错误，请重新签到", allow_sending_without_reply=True)

    async def process_validate(self, message: Message, user: User, bot_username: Optional[str] = None):
        try:
            client = await get_genshin_client(user.id)
            if client.region != Region.CHINESE:
                await message.reply_text("非法用户")
                return
        except UserNotFoundError:
            await message.reply_text("用户未找到")
            return
        except CookiesNotFoundError:
            await message.reply_text("检测到用户为UID绑定，无需认证")
            return
        try:
            await client.get_genshin_notes()
        except GenshinException as exc:
            if exc.retcode != 1034:
                raise exc
        else:
            await message.reply_text("账户正常，无需认证")
            return
        await message.reply_text(
            "由于官方对第三方工具限制以及账户安全的考虑，频繁使用第三方工具会导致账号被风控并要求用过验证才能进行访问。\n"
            "如果出现频繁验证请求，建议暂停使用本Bot在内的第三方工具查询功能。\n"
            "在暂停使用期间依然出现频繁认证，建议修改密码以保护账号安全。"
        )
        verification = Verification(cookies=client.cookie_manager.cookies)
        try:
            data = await verification.create(is_high=True)
            challenge = data["challenge"]
            gt = data["gt"]
            logger.success("用户 %s[%s] 创建验证成功\ngt:%s\nchallenge%s", user.full_name, user.id, gt, challenge)
        except ResponseException as exc:
            logger.warning("用户 %s[%s] 创建验证失效 API返回 [%s]%s", user.full_name, user.id, exc.code, exc.message)
            await message.reply_text(f"验证失败 错误信息为 [{exc.code}]{exc.message}")
            return
        try:
            validate = await verification.ajax(referer="https://webstatic.mihoyo.com/", gt=gt, challenge=challenge)
            if validate:
                await verification.verify(challenge, validate)
                logger.success("用户 %s[%s] 通过 ajax 验证", user.full_name, user.id)
                await message.reply_text("验证成功")
                return
        except APIHelperException as exc:
            logger.warning("用户 %s[%s] ajax 验证失效 错误信息为 %s", user.full_name, user.id, repr(exc))
        await self.verification_system.set_challenge(client.uid, gt, challenge)
        url = f"{config.pass_challenge_user_web}/webapp?username={bot_username}&command=verify&gt={gt}&challenge={challenge}&uid={client.uid}"
        await message.reply_text(
            "请尽快在10秒内完成手动验证\n或发送 /web_cancel 取消操作",
            reply_markup=ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text="点我手动验证",
                    web_app=WebAppInfo(url=url),
                )
            ),
        )
