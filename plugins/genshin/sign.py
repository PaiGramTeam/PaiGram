import datetime
from typing import Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.ext import MessageHandler, filters
from telegram.helpers import create_deep_linked_url

from core.config import config
from core.plugin import Plugin, handler
from core.services.sign.models import Sign as SignUser, SignStatusEnum
from core.services.sign.services import SignServices
from core.services.users.services import UserAdminService
from plugins.tools.genshin import GenshinHelper, CookiesNotFoundError, UserNotFoundError
from plugins.tools.sign import SignSystem, NeedChallenge
from utils.log import logger


class Sign(Plugin):
    """每日签到"""

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    def __init__(
        self,
        genshin_helper: GenshinHelper,
        sign_service: SignServices,
        user_admin_service: UserAdminService,
        sign_system: SignSystem,
    ):
        self.user_admin_service = user_admin_service
        self.sign_service = sign_service
        self.sign_system = sign_system
        self.genshin_helper = genshin_helper

    async def _process_auto_sign(self, user_id: int, chat_id: int, method: str) -> str:
        try:
            await self.genshin_helper.get_genshin_client(user_id)
        except (UserNotFoundError, CookiesNotFoundError):
            return "未查询到账号信息，请先私聊派蒙绑定账号"
        user: SignUser = await self.sign_service.get_by_user_id(user_id)
        if user:
            if method == "关闭":
                await self.sign_service.remove(user)
                return "关闭自动签到成功"
            if method == "开启":
                if user.chat_id == chat_id:
                    return "自动签到已经开启过了"
                user.chat_id = chat_id
                user.status = SignStatusEnum.STATUS_SUCCESS
                await self.sign_service.update(user)
                return "修改自动签到通知对话成功"
        elif method == "关闭":
            return "您还没有开启自动签到"
        elif method == "开启":
            user = SignUser(
                user_id=user_id,
                chat_id=chat_id,
                time_created=datetime.datetime.now(),
                status=SignStatusEnum.STATUS_SUCCESS,
            )
            await self.sign_service.add(user)
            return "开启自动签到成功"

    @handler(CommandHandler, command="sign", block=False)
    @handler(MessageHandler, filters=filters.Regex("^每日签到(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = self.get_args(context)
        validate: Optional[str] = None
        if len(args) >= 1:
            msg = None
            if args[0] == "开启自动签到":
                if await self.user_admin_service.is_admin(user.id):
                    msg = await self._process_auto_sign(user.id, message.chat_id, "开启")
                else:
                    msg = await self._process_auto_sign(user.id, user.id, "开启")
            elif args[0] == "关闭自动签到":
                msg = await self._process_auto_sign(user.id, message.chat_id, "关闭")
            else:
                validate = args[0]
            if msg:
                logger.info("用户 %s[%s] 自动签到命令请求 || 参数 %s", user.full_name, user.id, args[0])
                reply_message = await message.reply_text(msg)
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply_message, delay=30)
                    self.add_delete_message_job(message.chat_id, delay=30)
                return
        logger.info("用户 %s[%s] 每日签到命令请求", user.full_name, user.id)
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
        try:
            client = await self.genshin_helper.get_genshin_client(user.id)
            await message.reply_chat_action(ChatAction.TYPING)
            _, challenge = await self.sign_system.get_challenge(client.uid)
            if validate:
                _, challenge = await self.sign_system.get_challenge(client.uid)
                if challenge:
                    sign_text = await self.sign_system.start_sign(client, challenge=challenge, validate=validate)
                else:
                    reply_message = await message.reply_text("请求已经过期", allow_sending_without_reply=True)
                    if filters.ChatType.GROUPS.filter(reply_message):
                        self.add_delete_message_job(reply_message)
                    return
            else:
                sign_text = await self.sign_system.start_sign(client)
            reply_message = await message.reply_text(sign_text, allow_sending_without_reply=True)
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(reply_message)
        except (UserNotFoundError, CookiesNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self.add_delete_message_job(reply_message, delay=30)

                self.add_delete_message_job(message.chat_id, delay=30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
        except NeedChallenge as exc:
            button = await self.sign_system.get_challenge_button(
                context.bot.username,
                exc.uid,
                user.id,
                exc.gt,
                exc.challenge,
                not filters.ChatType.PRIVATE.filter(message),
            )
            reply_message = await message.reply_text(
                f"UID {exc.uid} 签到失败，触发验证码风控，请尝试点击下方按钮重新签到", allow_sending_without_reply=True, reply_markup=button
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(reply_message)

    @handler(CallbackQueryHandler, pattern=r"^sign\|", block=False)
    async def sign_gen_link(self, update: Update, context: CallbackContext) -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        async def get_sign_callback(callback_query_data: str) -> Tuple[int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            logger.debug("get_sign_callback 函数返回 user_id[%s] uid[%s]", _user_id, _uid)
            return _user_id, _uid

        user_id, uid = await get_sign_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        _, challenge = await self.sign_system.get_challenge(uid)
        if not challenge:
            await callback_query.answer(text="验证请求已经过期，请重新发起签到！", show_alert=True)
            return
        await callback_query.answer(url=create_deep_linked_url(context.bot.username, "sign"))
