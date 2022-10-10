import datetime
import json
import re
import time
from json import JSONDecodeError
from typing import Optional, Dict

from genshin import Game, GenshinException, AlreadyClaimed, Client
from httpx import AsyncClient, TimeoutException
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext
from telegram.ext import MessageHandler, filters

from core.admin.services import BotAdminService
from core.baseplugin import BasePlugin
from core.config import config
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

    def __init__(
        self,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        sign_service: SignServices = None,
        bot_admin_service: BotAdminService = None,
    ):
        self.bot_admin_service = bot_admin_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_service = sign_service

    @staticmethod
    async def pass_challenge(gt: str, challenge: str, referer: str = None) -> Optional[Dict]:
        """尝试自动通过验证，感谢项目 AutoMihoyoBBS 的贡献者 和 @coolxitech 大佬提供的方案

        https://github.com/coolxitech/mihoyo
        """
        if not gt or not challenge:
            return None
        if not referer:
            referer = (
                "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?"
                "bbs_auth_required=true&act_id=e202009291139501&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
            )
        header = {
            "Accept": "*/*",
            "X-Requested-With": "com.mihoyo.hyperion",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/2.37.1",
            "Referer": referer,
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        # ajax auto pass
        try:
            async with AsyncClient() as client:
                # gt={gt}&challenge={challenge}&lang=zh-cn&pt=3
                # client_type=web_mobile&callback=geetest_{int(time.time() * 1000)}
                req = await client.get(
                    "https://api.geetest.com/ajax.php",
                    params={
                        "gt": gt,
                        "challenge": challenge,
                        "lang": "zh-cn",
                        "pt": 3,
                        "client_type": "web_mobile",
                        "callback": f"geetest_{int(time.time() * 1000)}",
                    },
                    headers=header,
                    timeout=20,
                )
            text = req.text
            logger.info(f"ajax 返回：{text}")
            if req.status_code != 200:
                raise RuntimeError
            text = re.findall(r"^.*?\((\{.*?)\)$", text)[0]
            data = json.loads(text)
            if "success" in data["status"] and "success" in data["data"]["result"]:
                return {
                    "x-rpc-challenge": challenge,
                    "x-rpc-validate": data["data"]["validate"],
                    "x-rpc-seccode": f'{data["data"]["validate"]}|jordan',
                }
        except JSONDecodeError:
            logger.warning(f"签到ajax自动通过JSON解析失败")
        except TimeoutException:
            logger.warning(f"签到ajax自动通过请求超时")
        except KeyError:
            logger.warning(f"签到ajax自动通过数据错误")
        except RuntimeError:
            logger.warning(f"签到ajax自动通过请求错误")
        logger.warning("ajax自动通过失败")
        if not config.pass_challenge_api:
            return None
        pass_challenge_params = {
            "gt": gt,
            "challenge": challenge,
            "referer": referer,
        }
        if config.pass_challenge_app_key:
            pass_challenge_params["appkey"] = config.pass_challenge_app_key
        # custom api auto pass
        try:
            async with AsyncClient() as client:
                resp = await client.post(
                    config.pass_challenge_api,
                    params=pass_challenge_params,
                    timeout=45,
                )
            logger.info(f"签到自定义打码平台返回：{resp.text}")
            data = resp.json()
            status = data.get("status")
            if status is not None:
                if status != 0:
                    logger.error(f"签到自定义打码平台解析错误：{data.get('msg')}")
            if data.get("code") != 0:
                raise RuntimeError
            return {
                "x-rpc-challenge": data["data"]["challenge"],
                "x-rpc-validate": data["data"]["validate"],
                "x-rpc-seccode": f'{data["data"]["validate"]}|jordan',
            }
        except JSONDecodeError:
            logger.warning(f"签到自定义打码平台JSON解析失败")
        except TimeoutException:
            logger.warning(f"签到自定义打码平台请求超时")
        except KeyError:
            logger.warning(f"签到自定义打码平台数据错误")
        except RuntimeError:
            logger.warning(f"签到自定义打码平台自动通过失败")
        return None

    @staticmethod
    async def _start_sign(client: Client) -> str:
        try:
            rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
        except GenshinException as error:
            logger.warning(f"UID {client.uid} 获取签到信息失败，API返回信息为 {str(error)}")
            return f"获取签到信息失败，API返回信息为 {str(error)}"
        try:
            daily_reward_info = await client.get_reward_info(game=Game.GENSHIN, lang="zh-cn")  # 获取签到信息失败
        except GenshinException as error:
            logger.warning(f"UID {client.uid} 获取签到状态失败，API返回信息为 {str(error)}")
            return f"获取签到状态失败，API返回信息为 {str(error)}"
        if not daily_reward_info.signed_in:
            try:
                request_daily_reward = await client.request_daily_reward(
                    "sign", method="POST", game=Game.GENSHIN, lang="zh-cn"
                )
                if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                    # 米游社国内签到自动打码
                    headers = await Sign.pass_challenge(
                        request_daily_reward.get("gt", ""),
                        request_daily_reward.get("challenge", ""),
                    )
                    if not headers:
                        logger.warning(f"UID {client.uid} 签到失败，触发验证码风控")
                        return f"UID {client.uid} 签到失败，触发验证码风控，请尝试重新签到。"
                    request_daily_reward = await client.request_daily_reward(
                        "sign",
                        method="POST",
                        game=Game.GENSHIN,
                        lang="zh-cn",
                        headers=headers,
                    )
                    if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                        logger.warning(f"UID {client.uid} 签到失败，触发验证码风控")
                        return f"UID {client.uid} 签到失败，触发验证码风控，请尝试重新签到。"
                    logger.info(f"UID {client.uid} 通过自动打码签到成功")
            except AlreadyClaimed:
                logger.info(f"UID {client.uid} 已经签到")
                result = "今天旅行者已经签到过了~"
            except GenshinException as error:
                logger.warning(f"UID {client.uid} 签到失败，API返回信息为 {str(error)}")
                return f"获取签到状态失败，API返回信息为 {str(error)}"
            else:
                logger.info(f"UID {client.uid} 签到成功")
                result = "OK"
        else:
            logger.info(f"UID {client.uid} 已经签到")
            result = "今天旅行者已经签到过了~"
        logger.info(f"UID {client.uid} 签到结果 {result}")
        reward = rewards[daily_reward_info.claimed_rewards - (1 if daily_reward_info.signed_in else 0)]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cn_timezone = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(cn_timezone)
        missed_days = now.day - daily_reward_info.claimed_rewards
        if not daily_reward_info.signed_in:
            missed_days -= 1
        message = (
            f"#### {today} (UTC+8) ####\n"
            f"UID: {client.uid}\n"
            f"今日奖励: {reward.name} × {reward.amount}\n"
            f"本月漏签次数：{missed_days}\n"
            f"签到结果: {result}"
        )
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
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = get_all_args(context)
        if len(args) >= 1:
            msg = None
            if args[0] == "开启自动签到":
                admin_list = await self.bot_admin_service.get_admin_list()
                if user.id in admin_list:
                    msg = await self._process_auto_sign(user.id, message.chat_id, "开启")
                else:
                    msg = await self._process_auto_sign(user.id, user.id, "开启")
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
            await message.reply_chat_action(ChatAction.TYPING)
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
