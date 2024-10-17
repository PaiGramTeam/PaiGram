import asyncio
import datetime
import random
import time
from typing import TYPE_CHECKING, Optional, List
from contextlib import asynccontextmanager

from simnet import Region
from simnet.client.components.lab import LabClient
from simnet.errors import BadRequest as SimnetBadRequest, TimedOut as SimnetTimedOut, InvalidCookies
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

from gram_core.basemodel import RegionEnum
from gram_core.plugin import Plugin, job, handler
from gram_core.services.cookies import CookiesService
from utils.log import logger

if TYPE_CHECKING:
    from gram_core.services.cookies.models import CookiesDataBase
    from telegram import Update
    from telegram.ext import ContextTypes
    from simnet.models.lab.accompany import AccompanyRole


class AccompanySystemError(Exception):
    def __init__(self, msg: str):
        self.msg = msg


class AccompanySystem(Plugin):
    def __init__(
        self,
        cookies_service: CookiesService,
    ):
        self.cookies_service = cookies_service
        self.accompany_roles = []

    @asynccontextmanager
    async def client(self, ck: "CookiesDataBase") -> LabClient:
        stoken = ck.data.get("stoken")
        if not stoken:
            raise AccompanySystemError("stoken is None")

        if ck.region == RegionEnum.HYPERION:  # 国服
            region = Region.CHINESE
        elif ck.region == RegionEnum.HOYOLAB:  # 国际服
            region = Region.OVERSEAS
        else:
            raise AccompanySystemError("Region is not None")

        async with LabClient(
            ck.data,
            region=region,
            account_id=ck.account_id,
            lang="zh-cn",
        ) as client:
            yield client

    @staticmethod
    async def request_accompany_role(client: "LabClient", role_id: int, topic_id: int) -> Optional["AccompanyRole"]:
        try:
            return await client.request_accompany_role(role_id, topic_id)
        except SimnetTimedOut:
            logger.warning("Account[%s] 陪伴 %s 失败，API请求超时", client.account_id, role_id)
            return None
        except InvalidCookies as exc:
            raise exc
        except SimnetBadRequest as error:
            logger.warning("Account[%s] 陪伴 %s 失败，API返回信息为 %s", client.account_id, role_id, str(error))
            return None

    async def start_accompany(
        self,
        client: "LabClient",
        is_sleep: bool = False,
        is_raise: bool = False,
    ) -> str:
        if is_sleep:
            await asyncio.sleep(random.randint(0, 3))  # nosec
        success, failed, coins = 0, 0, 0
        try:
            if not self.accompany_roles:
                self.accompany_roles = await client.get_accompany_roles()
            for role in self.accompany_roles:
                data = await self.request_accompany_role(client, role.role_id, role.topic_id)
                if data and data.increase_accompany_point:
                    success += 1
                    coins += data.increase_accompany_point
                else:
                    failed += 1
        except SimnetTimedOut as error:
            logger.warning("Account[%s] 获取陪伴信息失败，API请求超时", client.account_id)
            if is_raise:
                raise error
            return "获取陪伴信息失败，API请求超时"
        except SimnetBadRequest as error:
            logger.warning("Account[%s] 获取陪伴信息失败，API返回信息为 %s", client.account_id, str(error))
            if is_raise:
                raise error
            return f"获取陪伴信息失败，API返回信息为 {str(error)}"
        if success == 0 and coins == 0 and is_raise:
            raise AccompanySystemError("共获得陪伴值 0 ，可能已经陪伴过了")
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        message = (
            f"#### 角色陪伴 ####\n"
            f"时间：{today} (UTC+8)\n"
            f"Account: {client.account_id}\n"
            f"陪伴成功: {success}\n"
            f"陪伴失败：{failed}\n"
            f"共获得陪伴值: {coins}"
        )
        return message

    async def _do_accompany_job(
        self, context: "ContextTypes.DEFAULT_TYPE", accompany_list: List["CookiesDataBase"], is_raise: bool = True
    ) -> None:
        for accompany_db in accompany_list:
            user_id = accompany_db.user_id
            text = None
            try:
                async with self.client(accompany_db) as client:
                    text = await self.start_accompany(client, is_sleep=True, is_raise=is_raise)
            except (AccompanySystemError, SimnetTimedOut, SimnetBadRequest):
                continue
            except Exception as exc:
                logger.error("执行自动角色陪伴时发生错误 user_id[%s]", user_id, exc_info=exc)
            if text:
                try:
                    await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
                except (BadRequest, Forbidden):
                    continue
                except Exception as exc:
                    logger.error("执行自动角色陪伴时发生错误 user_id[%s]", user_id, exc_info=exc)

    async def do_accompany_job(self, context: "ContextTypes.DEFAULT_TYPE") -> None:
        accompany_list = await self.cookies_service.get_all(region=RegionEnum.HOYOLAB)
        await self._do_accompany_job(context, accompany_list)

    @job.run_daily(time=datetime.time(hour=1, minute=1, second=0), name="AccompanyJob")
    async def accompany(self, context: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行自动角色陪伴")
        await self.do_accompany_job(context)
        logger.success("执行自动角色陪伴完成")

    @handler.command(command="accompany_all", block=False, admin=True)
    async def accompany_all(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        logger.info("用户 %s[%s] accompany_all 命令请求", user.full_name, user.id)
        message = update.effective_message
        reply = await message.reply_text("正在全部重新角色陪伴，请稍后...")
        await self.do_accompany_job(context)
        await reply.edit_text("全部账号重新角色陪伴完成")

    @handler.command(command="accompany", cookie=True, block=False)
    async def accompany_someone(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        logger.info("用户 %s 请求角色陪伴", user_id)
        message = update.effective_message
        reply = await message.reply_text("正在角色陪伴，请稍后...")
        ck = await self.cookies_service.get_all(user_id=user_id, region=RegionEnum.HOYOLAB)
        if not ck:
            await reply.edit_text("未绑定国际服账号")
            return
        await self._do_accompany_job(context, ck, is_raise=False)
        await reply.edit_text("角色陪伴完成")
