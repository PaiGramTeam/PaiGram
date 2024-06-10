from typing import Optional, Tuple

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.config import config
from core.handler.callbackqueryhandler import CallbackQueryHandler
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.task.models import Task as SignUser, TaskStatusEnum
from core.services.task.services import SignServices
from core.services.users.services import UserAdminService
from plugins.tools.genshin import GenshinHelper
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
        player: PlayersService,
        cookies: CookiesService,
    ):
        self.user_admin_service = user_admin_service
        self.sign_service = sign_service
        self.sign_system = sign_system
        self.genshin_helper = genshin_helper
        self.players_service = player
        self.cookies_service = cookies

    async def _process_auto_sign(self, user_id: int, chat_id: int, method: str) -> str:
        player = await self.players_service.get_player(user_id)
        if player is None:
            return config.notice.user_not_found
        cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookie_model is None:
            return config.notice.user_not_found
        user: SignUser = await self.sign_service.get_by_user_id(user_id)
        if user:
            if method == "关闭":
                await self.sign_service.remove(user)
                return "关闭自动签到成功"
            if method == "开启":
                if user.chat_id == chat_id:
                    return "自动签到已经开启过了"
                user.chat_id = chat_id
                user.status = TaskStatusEnum.STATUS_SUCCESS
                await self.sign_service.update(user)
                return "修改自动签到通知对话成功"
        elif method == "关闭":
            return "您还没有开启自动签到"
        elif method == "开启":
            user = self.sign_service.create(user_id, chat_id, TaskStatusEnum.STATUS_SUCCESS)
            await self.sign_service.add(user)
            return "开启自动签到成功"

    @handler.command(command="sign", cookie=True, block=False)
    @handler.message(filters=filters.Regex("^每日签到(.*)"), cookie=True, block=False)
    @handler.command(command="start", filters=filters.Regex("sign$"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        args = self.get_args(context)
        validate: Optional[str] = None
        if len(args) >= 1:
            msg = None
            if args[0] == "开启自动签到":
                if await self.user_admin_service.is_admin(user_id):
                    msg = await self._process_auto_sign(user_id, message.chat_id, "开启")
                else:
                    msg = await self._process_auto_sign(user_id, user_id, "开启")
            elif args[0] == "关闭自动签到":
                msg = await self._process_auto_sign(user_id, message.chat_id, "关闭")
            elif args[0] != "sign":
                validate = args[0]
            if msg:
                self.log_user(update, logger.info, "自动签到命令请求 || 参数 %s", args[0])
                reply_message = await message.reply_text(msg)
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply_message, delay=30)
                    self.add_delete_message_job(message, delay=30)
                return
        self.log_user(update, logger.info, "每日签到命令请求")
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
        try:
            async with self.genshin_helper.genshin(user_id) as client:
                await message.reply_chat_action(ChatAction.TYPING)
                _, challenge = await self.sign_system.get_challenge(client.player_id)
                if validate:
                    _, challenge = await self.sign_system.get_challenge(client.player_id)
                    if challenge:
                        sign_text = await self.sign_system.start_sign(client, challenge=challenge, validate=validate)
                    else:
                        reply_message = await message.reply_text("请求已经过期")
                        if filters.ChatType.GROUPS.filter(reply_message):
                            self.add_delete_message_job(reply_message)
                        return
                else:
                    sign_text = await self.sign_system.start_sign(client)
            reply_message = await message.reply_text(sign_text)
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(reply_message)
        except NeedChallenge as exc:
            button = await self.sign_system.get_challenge_button(
                context.bot.username,
                exc.uid,
                user_id,
                exc.gt,
                exc.challenge,
                not filters.ChatType.PRIVATE.filter(message),
            )
            reply_message = await message.reply_text(
                "签到失败，触发验证码风控，请尝试点击下方按钮重新签到",
                reply_markup=button,
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(reply_message)

    @handler.command(command="start", filters=filters.Regex(r" challenge_sign_(.*)"), block=False)
    async def command_challenge(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = context.args
        _data = args[0].split("_")
        validate = _data[2]
        logger.info("用户 %s[%s] 通过start命令 进入签到流程", user.full_name, user.id)
        try:
            async with self.genshin_helper.genshin(user.id) as client:
                await message.reply_chat_action(ChatAction.TYPING)
                _, challenge = await self.sign_system.get_challenge(client.player_id)
                if not challenge:
                    await message.reply_text("验证请求已过期。")
                    return
                sign_text = await self.sign_system.start_sign(client, challenge=challenge, validate=validate)
                await message.reply_text(sign_text)
        except NeedChallenge:
            await message.reply_text("回调错误，请重新签到")

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
