import time
from contextlib import asynccontextmanager
from typing import Optional, List, TYPE_CHECKING

from simnet.errors import BadRequest as SimnetBadRequest, InvalidCookies, AlreadyClaimed, TimedOut as SimnetTimedOut
from simnet.models.cloud_game.base import CloudGameWallet
from sqlalchemy.orm.exc import StaleDataError
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

from gram_core.basemodel import RegionEnum
from gram_core.plugin import Plugin
from gram_core.services.task.models import TaskStatusEnum
from gram_core.services.task.services import TaskCardServices
from plugins.tools.genshin import GenshinHelper, CookiesUpdateRequestError, PlayerNotFoundError, CookiesNotFoundError
from plugins.tools.sign import SignJobType
from utils.log import logger

if TYPE_CHECKING:
    from simnet import GenshinClient
    from telegram.ext import ContextTypes


class CloudGameHelper(Plugin):
    def __init__(self, genshin_helper: GenshinHelper, sign_service: TaskCardServices):
        self.genshin_helper = genshin_helper
        self.sign_service = sign_service

    @asynccontextmanager
    async def client(  # skipcq: PY-R1000 #
        self, user_id: int, region: Optional[RegionEnum] = None, player_id: int = None, offset: int = 0
    ) -> "GenshinClient":
        async with self.genshin_helper.genshin(user_id, region, player_id, offset) as client:
            client: "GenshinClient"
            try:
                yield client
            except InvalidCookies as exc:
                stoken = client.cookies.get("stoken")
                combo_token = None
                if stoken is not None:
                    try:
                        game_token = await client.get_game_token_by_stoken()
                        logger.success("用户 %s 获取 game_token 成功", user_id)
                        login_cookie = await client.login_game_by_game_token(game_token)
                        logger.success("用户 %s 刷新 combo_token 成功", user_id)
                        combo_token = login_cookie.combo_token
                    except Exception as _exc:
                        logger.error("用户 %s 刷新 combo_token 失败", user_id, exc_info=_exc)
                if combo_token:
                    raise CookiesUpdateRequestError({client.cloud_game_combo_token_key: combo_token})
                raise exc

    @staticmethod
    async def clear_notification(client: "GenshinClient"):
        no = await client.get_cloud_game_notifications()
        data_list = no.get("list")
        if not data_list:
            return
        for data in data_list:
            n_id = data.get("id")
            if not n_id:
                continue
            await client.ask_cloud_game_notifications(n_id)

    @staticmethod
    async def get_wallet(client: "GenshinClient") -> CloudGameWallet:
        await client.check_cloud_game_token()
        return await client.get_cloud_game_wallet()

    async def start_sign(
        self,
        client: "GenshinClient",
        is_raise: bool = False,
        title: Optional[str] = "云游戏签到结果",
    ) -> str:
        try:
            wallet = await self.get_wallet(client)
        except InvalidCookies as error:
            logger.warning("UID[%s] 获取云游戏钱包信息失败，API返回信息为 %s", client.player_id, str(error))
            raise error
        except SimnetBadRequest as error:
            logger.warning("UID[%s] 获取云游戏钱包信息失败，API返回信息为 %s", client.player_id, str(error))
            if is_raise:
                raise error
            return f"获取云游戏钱包信息失败，API返回信息为 {str(error)}"
        try:
            await self.clear_notification(client)
        except Exception:
            logger.warning("UID[%s] 清空云游戏通知失败", client.player_id)
        have_free_time = wallet.free_time.free_time
        limit_time = wallet.free_time.free_time_limit
        if have_free_time == limit_time:
            logger.success("UID[%s] 云游戏签到超出免费时长上限", client.player_id)
            result = "超出免费时长上限"
        else:
            logger.success("UID[%s] 云游戏签到成功", client.player_id)
            result = "OK"
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        message = (
            f"#### {title} ####\n"
            f"时间：{today} (UTC+8)\n"
            f"Account: {client.account_id}\n"
            f"免费时长：{have_free_time} 分钟\n"
            f"签到结果: {result}"
        )
        return message

    async def do_sign_job(self, context: "ContextTypes.DEFAULT_TYPE", job_type: SignJobType):  # skipcq: PY-R1000 #
        include_status: List[TaskStatusEnum] = [
            TaskStatusEnum.STATUS_SUCCESS,
            TaskStatusEnum.ALREADY_CLAIMED,
            TaskStatusEnum.TIMEOUT_ERROR,
            TaskStatusEnum.NEED_CHALLENGE,
            TaskStatusEnum.GENSHIN_EXCEPTION,
        ]
        if job_type == SignJobType.START:
            title = "自动签到"
        elif job_type == SignJobType.REDO:
            title = "自动重新签到"
            include_status.remove(TaskStatusEnum.STATUS_SUCCESS)
        else:
            raise ValueError
        sign_list = await self.sign_service.get_all()
        for sign_db in sign_list:
            if sign_db.status not in include_status:
                continue
            user_id = sign_db.user_id
            player_id = sign_db.player_id
            try:
                async with self.client(user_id, player_id=player_id) as client:
                    text = await self.start_sign(client, is_raise=True, title=title)
            except InvalidCookies:
                text = "云游戏自动签到执行失败，Cookie无效"
                sign_db.status = TaskStatusEnum.INVALID_COOKIES
            except AlreadyClaimed:
                text = "今天旅行者云游戏已经签到过了~"
                sign_db.status = TaskStatusEnum.ALREADY_CLAIMED
            except SimnetBadRequest as exc:
                text = f"云游戏自动签到执行失败，API返回信息为 {str(exc)}"
                sign_db.status = TaskStatusEnum.GENSHIN_EXCEPTION
            except SimnetTimedOut:
                text = "云游戏签到失败了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ "
                sign_db.status = TaskStatusEnum.TIMEOUT_ERROR
            except PlayerNotFoundError:
                logger.info("用户 user_id[%s] 玩家不存在 关闭并移除云游戏自动签到", user_id)
                await self.sign_service.remove(sign_db)
                continue
            except CookiesNotFoundError:
                logger.info("用户 user_id[%s] cookie 不存在 关闭并移除云游戏自动签到", user_id)
                await self.sign_service.remove(sign_db)
                continue
            except Exception as exc:
                logger.error("执行云游戏自动签到时发生错误 user_id[%s]", user_id, exc_info=exc)
                text = "签到失败了呜呜呜 ~ 执行云游戏自动签到时发生错误"
            else:
                sign_db.status = TaskStatusEnum.STATUS_SUCCESS
            if sign_db.chat_id < 0:
                text = f'<a href="tg://user?id={sign_db.user_id}">NOTICE {sign_db.user_id}</a>\n\n{text}'
            try:
                await context.bot.send_message(sign_db.chat_id, text, parse_mode=ParseMode.HTML)
            except BadRequest as exc:
                logger.error("执行云游戏自动签到时发生错误 user_id[%s] Message[%s]", user_id, exc.message)
                sign_db.status = TaskStatusEnum.BAD_REQUEST
            except Forbidden as exc:
                logger.error("执行云游戏自动签到时发生错误 user_id[%s] message[%s]", user_id, exc.message)
                sign_db.status = TaskStatusEnum.FORBIDDEN
            except Exception as exc:
                logger.error("执行云游戏自动签到时发生错误 user_id[%s]", user_id, exc_info=exc)
                continue
            else:
                if sign_db.status not in include_status:
                    sign_db.status = TaskStatusEnum.STATUS_SUCCESS
            try:
                await self.sign_service.update(sign_db)
            except StaleDataError:
                logger.warning("用户 user_id[%s] 云游戏自动签到数据过期，跳过更新数据", user_id)
