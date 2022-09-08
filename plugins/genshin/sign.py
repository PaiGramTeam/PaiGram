import datetime
import time

from genshin import Game, GenshinException, AlreadyClaimed, Client
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters

from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.sign.models import Sign as SignUser, SignStatusEnum
from core.sign.services import SignServices
from core.user.error import UserNotFoundError
from core.user.services import UserService
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class Sign(Plugin, BasePlugin):
    """每日签到"""

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None,
                 sign_service: SignServices = None):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_service = sign_service

    @staticmethod
    async def _start_sign(client: Client) -> str:
        try:
            rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
        except GenshinException as error:
            logger.error(f"UID {client.uid} 获取签到信息失败，API返回信息为 {str(error)}")
            return f"获取签到信息失败，API返回信息为 {str(error)}"
        try:
            daily_reward_info = await client.get_reward_info(game=Game.GENSHIN, lang="zh-cn")  # 获取签到信息失败
        except GenshinException as error:
            logger.error(f"UID {client.uid} 获取签到状态失败，API返回信息为 {str(error)}")
            return f"获取签到状态失败，API返回信息为 {str(error)}"
        if not daily_reward_info.signed_in:
            try:
                request_daily_reward = await client.request_daily_reward("sign", method="POST",
                                                                         game=Game.GENSHIN, lang="zh-cn")
                logger.info(f"UID {client.uid} 签到请求 {request_daily_reward}")
                if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                    logger.warning(f"UID {client.uid} 签到失败，触发验证码风控")
                    return f"UID {client.uid} 签到失败，触发验证码风控，请尝试重新签到。"
            except AlreadyClaimed:
                result = "今天旅行者已经签到过了~"
            except GenshinException as error:
                logger.error(f"UID {client.uid} 签到失败，API返回信息为 {str(error)}")
                return f"获取签到状态失败，API返回信息为 {str(error)}"
            else:
                result = "OK"
        else:
            result = "今天旅行者已经签到过了~"
        logger.info(f"UID {client.uid} 签到结果 {result}")
        reward = rewards[daily_reward_info.claimed_rewards - (1 if daily_reward_info.signed_in else 0)]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cn_timezone = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(cn_timezone)
        missed_days = now.day - daily_reward_info.claimed_rewards
        if not daily_reward_info.signed_in:
            missed_days -= 1
        message = f"#### {today} (UTC+8) ####\n" \
                  f"UID: {client.uid}\n" \
                  f"今日奖励: {reward.name} × {reward.amount}\n" \
                  f"本月漏签次数：{missed_days}\n" \
                  f"签到结果: {result}"
        return message

    async def _process_auto_sign(self, user_id: int, chat_id: int, method: str) -> str:
        try:
            await get_genshin_client(user_id)
        except (UserNotFoundError, CookiesNotFoundError):
            return "未查询到账号信息，请先私聊派蒙绑定账号"
        user: SignUser = await self.sign_service.get_by_user_id(user_id)
        if user:
            if method == "关闭":
                await self.sign_service.remove(user)
                return "关闭自动签到成功"
            elif method == "开启":
                if user.chat_id == chat_id:
                    return "自动签到已经开启过了"
                user.chat_id = chat_id
                await self.sign_service.update(user)
                return "修改自动签到通知对话成功"
        elif method == "关闭":
            return "您还没有开启自动签到"
        elif method == "开启":
            user = SignUser(user_id=user_id, chat_id=chat_id, time_created=datetime.datetime.now(),
                            status=SignStatusEnum.STATUS_SUCCESS)
            await self.sign_service.add(user)
            return "开启自动签到成功"

    @handler(CommandHandler, command="sign", block=False)
    @handler(MessageHandler, filters=filters.Regex("^每日签到(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = get_all_args(context)
        if len(args) >= 1:
            msg = None
            if args[0] == "开启自动签到":
                msg = await self._process_auto_sign(user.id, message.chat_id, "开启")
            elif args[0] == "关闭自动签到":
                msg = await self._process_auto_sign(user.id, message.chat_id, "关闭")
            if msg:
                logger.info(f"用户 {user.full_name}[{user.id}] 自动签到命令请求 || 参数 {args[0]}")
                reply_message = await message.reply_text(msg)
                if filters.ChatType.GROUPS.filter(message):
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                    self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
                return
        logger.info(f"用户 {user.full_name}[{user.id}] 每日签到命令请求")
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, message.chat_id, message.message_id)
        try:
            client = await get_genshin_client(user.id)
            sign_text = await self._start_sign(client)
            reply_message = await message.reply_text(sign_text, allow_sending_without_reply=True)
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
        except (UserNotFoundError, CookiesNotFoundError):
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
