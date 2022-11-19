import asyncio
import datetime
import random
import time
from json import JSONDecodeError
from typing import Optional, Tuple

from genshin import Game, GenshinException, AlreadyClaimed, Client
from genshin.utility import recognize_genshin_server
from httpx import AsyncClient, TimeoutException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.ext import MessageHandler, filters

from core.admin.services import BotAdminService
from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.bot import bot
from core.config import config
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.sign.models import Sign as SignUser, SignStatusEnum
from core.sign.services import SignServices
from core.user.error import UserNotFoundError
from core.user.services import UserService
from modules.apihelper.hyperion import Verification
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class NeedChallenge(Exception):
    def __init__(self, uid: int, gt: str = "", challenge: str = ""):
        super().__init__()
        self.uid = uid
        self.gt = gt
        self.challenge = challenge


class SignSystem:
    REFERER = (
        "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?"
        "bbs_auth_required=true&act_id=e202009291139501&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
    )

    def __init__(self, redis: RedisDB):
        self.cache = redis.client
        self.qname = "plugin:sign:"
        self.verification = Verification()

    async def get_challenge(self, uid: int) -> Tuple[Optional[str], Optional[str]]:
        data = await self.cache.get(f"{self.qname}{uid}")
        if not data:
            return None, None
        data = data.decode("utf-8").split("|")
        return data[0], data[1]

    async def set_challenge(self, uid: int, gt: str, challenge: str):
        await self.cache.set(f"{self.qname}{uid}", f"{gt}|{challenge}")
        await self.cache.expire(f"{self.qname}{uid}", 10 * 60)

    async def get_challenge_button(
        self, uid: int, user_id: int, gt: Optional[str] = None, challenge: Optional[str] = None, callback: bool = True
    ) -> Optional[InlineKeyboardMarkup]:
        if not config.pass_challenge_user_web:
            return None
        if challenge and gt:
            await self.set_challenge(uid, gt, challenge)
        if not challenge or not gt:
            gt, challenge = await self.get_challenge(uid)
        if not challenge or not gt:
            return None
        if callback:
            data = f"sign|{user_id}|{uid}"
            return InlineKeyboardMarkup([[InlineKeyboardButton("请尽快点我进行手动验证", callback_data=data)]])
        else:
            url = f"{config.pass_challenge_user_web}?username={bot.app.bot.username}&command=sign&gt={gt}&challenge={challenge}&uid={uid}"
            return InlineKeyboardMarkup([[InlineKeyboardButton("请尽快点我进行手动验证", url=url)]])

    async def recognize(self, gt: str, challenge: str, referer: str = None) -> Optional[str]:
        if not referer:
            referer = self.REFERER
        if not gt or not challenge:
            return None
        pass_challenge_params = {
            "gt": gt,
            "challenge": challenge,
            "referer": referer,
        }
        if config.pass_challenge_app_key:
            pass_challenge_params["appkey"] = config.pass_challenge_app_key
        headers = {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
        }
        try:
            async with AsyncClient(headers=headers) as client:
                resp = await client.post(
                    config.pass_challenge_api,
                    params=pass_challenge_params,
                    timeout=60,
                )
            logger.debug("recognize 请求返回：%s", resp.text)
            data = resp.json()
            status = data.get("status")
            if status != 0:
                logger.error("recognize 解析错误：[%s]%s", data.get('code'), data.get('msg'))
            if data.get("code", 0) != 0:
                raise RuntimeError
            logger.info("recognize 解析成功")
            return data["data"]["validate"]
        except JSONDecodeError:
            logger.warning("recognize 请求 JSON 解析失败")
        except TimeoutException as exc:
            logger.warning("recognize 请求超时")
            raise exc
        except KeyError:
            logger.warning("recognize 请求数据错误")
        except RuntimeError:
            logger.warning("recognize 请求失败")
        return None

    async def start_sign(
        self,
        client: Client,
        challenge: Optional[str] = None,
        validate: Optional[str] = None,
        is_sleep: bool = False,
        is_raise: bool = False,
        title: Optional[str] = "签到结果",
    ) -> str:
        if is_sleep:
            if recognize_genshin_server(client.uid) in ("cn_gf01", "cn_qd01"):
                await asyncio.sleep(random.randint(10, 300))  # nosec
            else:
                await asyncio.sleep(random.randint(0, 3))  # nosec
        try:
            rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
        except GenshinException as error:
            logger.warning("UID[%s] 获取签到信息失败，API返回信息为 %s", client.uid, str(error))
            if is_raise:
                raise error
            return f"获取签到信息失败，API返回信息为 {str(error)}"
        try:
            daily_reward_info = await client.get_reward_info(game=Game.GENSHIN, lang="zh-cn")  # 获取签到信息失败
        except GenshinException as error:
            logger.warning("UID[%s] 获取签到状态失败，API返回信息为 %s", client.uid, str(error))
            if is_raise:
                raise error
            return f"获取签到状态失败，API返回信息为 {str(error)}"
        if not daily_reward_info.signed_in:
            try:
                if validate:
                    logger.info("UID[%s] 正在尝试通过验证码\nchallenge[%s]\nvalidate[%s]", client.uid, challenge, validate)
                request_daily_reward = await client.request_daily_reward(
                    "sign",
                    method="POST",
                    game=Game.GENSHIN,
                    lang="zh-cn",
                    challenge=challenge,
                    validate=validate,
                )
                logger.debug("request_daily_reward 返回 %s", request_daily_reward)
                if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                    # 尝试通过 ajax 请求绕过签到
                    gt = request_daily_reward.get("gt", "")
                    challenge = request_daily_reward.get("challenge", "")
                    logger.warning("UID[%s] 触发验证码\ngt[%s]\nchallenge[%s]", client.uid, gt, challenge)
                    validate = await self.verification.ajax(
                        referer=self.REFERER,
                        gt=gt,
                        challenge=challenge,
                    )
                    if validate:
                        logger.success("ajax 通过验证成功\nchallenge[%s]\nvalidate[%s]", challenge, validate)
                        request_daily_reward = await client.request_daily_reward(
                            "sign",
                            method="POST",
                            game=Game.GENSHIN,
                            lang="zh-cn",
                            challenge=challenge,
                            validate=validate,
                        )
                        logger.debug("request_daily_reward 返回 %s", request_daily_reward)
                        if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                            logger.warning("UID[%s] 触发验证码\nchallenge[%s]", client.uid, challenge)
                            raise NeedChallenge(
                                uid=client.uid,
                                gt=request_daily_reward.get("gt", ""),
                                challenge=request_daily_reward.get("challenge", ""),
                            )
                    elif config.pass_challenge_app_key:
                        # 如果无法绕过 检查配置文件是否配置识别 API 尝试请求绕过
                        # 注意 需要重新获取没有进行任何请求的 Challenge
                        logger.info("UID[%s] 正在使用 recognize 重新请求签到", client.uid)
                        _request_daily_reward = await client.request_daily_reward(
                            "sign",
                            method="POST",
                            game=Game.GENSHIN,
                            lang="zh-cn",
                        )
                        logger.debug("request_daily_reward 返回\n%s", _request_daily_reward)
                        if _request_daily_reward and _request_daily_reward.get("success", 0) == 1:
                            _gt = _request_daily_reward.get("gt", "")
                            _challenge = _request_daily_reward.get("challenge", "")
                            logger.info("UID[%s] 创建验证码\ngt[%s]\nchallenge[%s]", client.uid, _gt, _challenge)
                            _validate = await self.recognize(_gt, _challenge)
                            if _validate:
                                logger.success("recognize 通过验证成功\nchallenge[%s]\nvalidate[%s]", _challenge, _validate)
                                request_daily_reward = await client.request_daily_reward(
                                    "sign",
                                    method="POST",
                                    game=Game.GENSHIN,
                                    lang="zh-cn",
                                    challenge=_challenge,
                                    validate=_validate,
                                )
                                if request_daily_reward and request_daily_reward.get("success", 0) == 1:
                                    logger.warning("UID[%s] 触发验证码\nchallenge[%s]", client.uid, _challenge)
                                    gt = request_daily_reward.get("gt", "")
                                    challenge = request_daily_reward.get("challenge", "")
                                    logger.success("UID[%s] 创建验证成功\ngt[%s]\nchallenge[%s]", client.uid, gt, challenge)
                                    raise NeedChallenge(
                                        uid=client.uid,
                                        gt=gt,
                                        challenge=challenge,
                                    )
                                else:
                                    logger.success("UID[%s] 通过 recognize 签到成功", client.uid)
                            else:
                                request_daily_reward = await client.request_daily_reward(
                                    "sign", method="POST", game=Game.GENSHIN, lang="zh-cn"
                                )
                                gt = request_daily_reward.get("gt", "")
                                challenge = request_daily_reward.get("challenge", "")
                                logger.success("UID[%s] 创建验证成功\ngt[%s]\nchallenge[%s]", client.uid, gt, challenge)
                                raise NeedChallenge(uid=client.uid, gt=gt, challenge=challenge)
                    else:
                        request_daily_reward = await client.request_daily_reward(
                            "sign", method="POST", game=Game.GENSHIN, lang="zh-cn"
                        )
                        gt = request_daily_reward.get("gt", "")
                        challenge = request_daily_reward.get("challenge", "")
                        logger.success("UID[%s] 创建验证成功\ngt[%s]\nchallenge[%s]", client.uid, gt, challenge)
                        raise NeedChallenge(uid=client.uid, gt=gt, challenge=challenge)
                else:
                    logger.success("UID[%s] 签到成功", client.uid)
            except TimeoutException as error:
                logger.warning("UID[%s] 签到请求超时", client.uid)
                if is_raise:
                    raise error
                return "签到失败了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ "
            except AlreadyClaimed as error:
                logger.warning("UID[%s] 已经签到", client.uid)
                if is_raise:
                    raise error
                result = "今天旅行者已经签到过了~"
            except GenshinException as error:
                logger.warning("UID %s 签到失败，API返回信息为 %s", client.uid, str(error))
                if is_raise:
                    raise error
                return f"获取签到状态失败，API返回信息为 {str(error)}"
            else:
                result = "OK"
        else:
            logger.info("UID[%s] 已经签到", client.uid)
            result = "今天旅行者已经签到过了~"
        logger.info("UID[%s] 签到结果 %s", client.uid, result)
        reward = rewards[daily_reward_info.claimed_rewards - (1 if daily_reward_info.signed_in else 0)]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cn_timezone = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(cn_timezone)
        missed_days = now.day - daily_reward_info.claimed_rewards
        if not daily_reward_info.signed_in:
            missed_days -= 1
        message = (
            f"#### {title} ####\n"
            f"时间：{today} (UTC+8)\n"
            f"UID: {client.uid}\n"
            f"今日奖励: {reward.name} × {reward.amount}\n"
            f"本月漏签次数：{missed_days}\n"
            f"签到结果: {result}"
        )
        return message


class Sign(Plugin, BasePlugin):
    """每日签到"""

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    def __init__(
        self,
        redis: RedisDB = None,
        user_service: UserService = None,
        cookies_service: CookiesService = None,
        sign_service: SignServices = None,
        bot_admin_service: BotAdminService = None,
    ):
        self.bot_admin_service = bot_admin_service
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.sign_service = sign_service
        self.system = SignSystem(redis)

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
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = get_all_args(context)
        validate: Optional[str] = None
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
            else:
                validate = args[0]
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
            _, challenge = await self.system.get_challenge(client.uid)
            if validate:
                _, challenge = await self.system.get_challenge(client.uid)
                if challenge:
                    sign_text = await self.system.start_sign(client, challenge=challenge, validate=validate)
                else:
                    reply_message = await message.reply_text("请求已经过期", allow_sending_without_reply=True)
                    if filters.ChatType.GROUPS.filter(reply_message):
                        self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
                    return
            else:
                sign_text = await self.system.start_sign(client)
            reply_message = await message.reply_text(sign_text, allow_sending_without_reply=True)
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
        except (UserNotFoundError, CookiesNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=f"https://t.me/{context.bot.username}?start=set_cookie")]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
        except NeedChallenge as exc:
            button = await self.system.get_challenge_button(
                exc.uid, user.id, exc.gt, exc.challenge, not filters.ChatType.PRIVATE.filter(message)
            )
            reply_message = await message.reply_text(
                f"UID {exc.uid} 签到失败，触发验证码风控，请尝试点击下方按钮重新签到", allow_sending_without_reply=True, reply_markup=button
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)

    @handler(CallbackQueryHandler, pattern=r"^sign\|", block=False)
    @restricts(restricts_time_of_groups=20, without_overlapping=True)
    @error_callable
    async def sign_gen_link(self, update: Update, _: CallbackContext) -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        async def get_sign_callback(callback_query_data: str) -> Tuple[int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            logger.debug(f"get_sign_callback 函数返回 user_id[{_user_id}] uid[{_uid}]")
            return _user_id, _uid

        user_id, uid = await get_sign_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" "再乱点再按我叫西风骑士团、千岩军、天领奉行和教令院了！", show_alert=True)
            return
        _, challenge = await self.system.get_challenge(uid)
        if not challenge:
            await callback_query.answer(text="验证请求已经过期，请重新发起签到！", show_alert=True)
            return
        url = f"t.me/{bot.app.bot.username}?start=sign"
        await callback_query.answer(url=url)
