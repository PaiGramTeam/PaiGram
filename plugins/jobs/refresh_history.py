import datetime
from asyncio import sleep
from typing import TYPE_CHECKING, List, Dict

from simnet.errors import (
    TimedOut as SimnetTimedOut,
    BadRequest as SimnetBadRequest,
    InvalidCookies,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

from core.plugin import Plugin, job
from core.services.history_data.services import (
    HistoryDataAbyssServices,
    HistoryDataLedgerServices,
    HistoryDataImgTheaterServices,
)
from gram_core.basemodel import RegionEnum
from gram_core.plugin import handler
from gram_core.services.cookies import CookiesService
from gram_core.services.cookies.models import CookiesStatusEnum
from plugins.genshin.abyss import AbyssPlugin
from plugins.genshin.ledger import LedgerPlugin
from plugins.genshin.role_combat import RoleCombatPlugin
from plugins.tools.genshin import GenshinHelper, PlayerNotFoundError, CookiesNotFoundError
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

    from simnet import GenshinClient

REGION = [RegionEnum.HYPERION, RegionEnum.HOYOLAB]
NOTICE_TEXT = """#### %s更新 ####
时间：%s (UTC+8)
UID: %s
结果: 新的%s已保存，可通过命令回顾"""


class RefreshHistoryJob(Plugin):
    """历史记录定时刷新"""

    def __init__(
        self,
        cookies: CookiesService,
        genshin_helper: GenshinHelper,
        history_abyss: HistoryDataAbyssServices,
        history_ledger: HistoryDataLedgerServices,
        history_img_theater: HistoryDataImgTheaterServices,
    ):
        self.cookies = cookies
        self.genshin_helper = genshin_helper
        self.history_data_abyss = history_abyss
        self.history_data_ledger = history_ledger
        self.history_data_img_theater = history_img_theater

    @staticmethod
    async def send_notice(context: "ContextTypes.DEFAULT_TYPE", user_id: int, notice_text: str):
        try:
            await context.bot.send_message(user_id, notice_text, parse_mode=ParseMode.HTML)
        except (BadRequest, Forbidden) as exc:
            logger.error("执行自动刷新历史记录时发生错误 user_id[%s] Message[%s]", user_id, exc.message)
        except Exception as exc:
            logger.error("执行自动刷新历史记录时发生错误 user_id[%s]", user_id, exc_info=exc)

    @staticmethod
    async def get_genshin_characters(client: "GenshinClient"):
        uid = client.player_id
        return await client.get_genshin_characters(uid, lang="zh-cn")

    async def save_abyss_data(self, client: "GenshinClient", avatar_data: Dict[int, int]) -> bool:
        uid = client.player_id
        abyss_data = await client.get_genshin_spiral_abyss(uid, previous=False, lang="zh-cn")
        if abyss_data.unlocked and abyss_data.ranks and abyss_data.ranks.most_kills:
            return await AbyssPlugin.save_abyss_data(self.history_data_abyss, uid, abyss_data, avatar_data)
        return False

    async def send_abyss_notice(self, context: "ContextTypes.DEFAULT_TYPE", user_id: int, uid: int):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notice_text = NOTICE_TEXT % ("深渊历史记录", now, uid, "挑战记录")
        await self.send_notice(context, user_id, notice_text)

    async def _save_ledger_data(self, client: "GenshinClient", month: int) -> bool:
        diary_info = await client.get_genshin_diary(client.player_id, month=month)
        return await LedgerPlugin.save_ledger_data(self.history_data_ledger, client.player_id, diary_info)

    @staticmethod
    def get_ledger_months() -> List[int]:
        now = datetime.datetime.now()
        now_time = (now - datetime.timedelta(days=1)) if now.day == 1 and now.hour <= 4 else now
        months = []
        last_month = now_time.replace(day=1) - datetime.timedelta(days=1)
        months.append(last_month.month)

        last_month = last_month.replace(day=1) - datetime.timedelta(days=1)
        months.append(last_month.month)
        return months

    async def save_ledger_data(self, client: "GenshinClient") -> bool:
        months = self.get_ledger_months()
        ok = False
        for month in months:
            if await self._save_ledger_data(client, month):
                ok = True
        return ok

    async def send_ledger_notice(self, context: "ContextTypes.DEFAULT_TYPE", user_id: int, uid: int):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notice_text = NOTICE_TEXT % ("旅行札记历史记录", now, uid, "旅行札记历史记录")
        await self.send_notice(context, user_id, notice_text)

    async def save_img_theater_data(self, client: "GenshinClient", avatar_data: Dict[int, int]) -> bool:
        uid = client.player_id
        abyss_data = await client.get_genshin_imaginarium_theater(uid, previous=False, lang="zh-cn")
        if abyss_data.unlocked and abyss_data.data:
            data = abyss_data.data[0]
            if data.has_data and data.has_detail_data and data.detail:
                return await RoleCombatPlugin.save_abyss_data(self.history_data_img_theater, uid, data, avatar_data)
        return False

    async def send_img_theater_notice(self, context: "ContextTypes.DEFAULT_TYPE", user_id: int, uid: int):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notice_text = NOTICE_TEXT % ("幻想真境剧诗历史记录", now, uid, "挑战记录")
        await self.send_notice(context, user_id, notice_text)

    @handler.command(command="remove_same_history", block=False, admin=True)
    async def remove_same_history(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        logger.info("用户 %s[%s] remove_same_history 命令请求", user.full_name, user.id)
        message = update.effective_message
        reply = await message.reply_text("正在执行移除相同数据历史记录任务，请稍后...")
        text = "移除相同数据历史记录任务完成\n"
        num1 = await self.history_data_abyss.remove_same_data()
        text += f"深渊数据移除数量：{num1}\n"
        num2 = await self.history_data_ledger.remove_same_data()
        text += f"旅行札记数据移除数量：{num2}\n"
        num3 = await self.history_data_img_theater.remove_same_data()
        text += f"幻想真境剧诗数据移除数量：{num3}\n"
        await reply.edit_text(text)

    @handler.command(command="refresh_all_history", block=False, admin=True)
    async def refresh_all_history(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        logger.info("用户 %s[%s] refresh_all_history 命令请求", user.full_name, user.id)
        message = update.effective_message
        reply = await message.reply_text("正在执行刷新历史记录任务，请稍后...")
        await self.daily_refresh_history(context)
        await reply.edit_text("全部账号刷新历史记录任务完成")

    @job.run_daily(time=datetime.time(hour=6, minute=1, second=0), name="RefreshHistoryJob")
    async def daily_refresh_history(self, context: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行每日刷新历史记录任务")
        for database_region in REGION:
            for cookie_model in await self.cookies.get_all(
                region=database_region, status=CookiesStatusEnum.STATUS_SUCCESS
            ):
                user_id = cookie_model.user_id
                try:
                    async with self.genshin_helper.genshin(user_id) as client:
                        if avatars := await self.get_genshin_characters(client):
                            avatar_data = {i.id: i.constellation for i in avatars}
                            if await self.save_abyss_data(client, avatar_data):
                                await self.send_abyss_notice(context, user_id, client.player_id)
                            if await self.save_img_theater_data(client, avatar_data):
                                await self.send_img_theater_notice(context, user_id, client.player_id)
                        if await self.save_ledger_data(client):
                            await self.send_ledger_notice(context, user_id, client.player_id)
                except (InvalidCookies, PlayerNotFoundError, CookiesNotFoundError):
                    continue
                except SimnetBadRequest as exc:
                    logger.warning(
                        "用户 user_id[%s] 请求历史记录失败 [%s]%s", user_id, exc.ret_code, exc.original or exc.message
                    )
                    continue
                except SimnetTimedOut:
                    logger.info("用户 user_id[%s] 请求历史记录超时", user_id)
                    continue
                except Exception as exc:
                    logger.error("执行自动刷新历史记录时发生错误 user_id[%s]", user_id, exc_info=exc)
                    continue
                await sleep(1)

        logger.success("执行每日刷新历史记录任务完成")
