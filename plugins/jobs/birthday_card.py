import datetime
from typing import TYPE_CHECKING

from core.plugin import Plugin, job
from plugins.tools.birthday_card import BirthdayCardSystem
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import ContextTypes


class CardJob(Plugin):
    def __init__(self, card_system: BirthdayCardSystem):
        self.card_system = card_system

    @job.run_daily(time=datetime.time(hour=0, minute=23, second=0), name="CardJob")
    async def card(self, context: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行自动领取生日画片")
        await self.card_system.do_get_card_job(context)
        logger.success("执行自动领取生日画片完成")
