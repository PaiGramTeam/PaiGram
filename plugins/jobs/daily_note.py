import datetime
from typing import TYPE_CHECKING

from core.plugin import Plugin, job
from plugins.tools.daily_note import DailyNoteSystem
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import ContextTypes


class NotesJob(Plugin):
    def __init__(self, daily_note_system: DailyNoteSystem):
        self.daily_note_system = daily_note_system

    @job.run_repeating(interval=datetime.timedelta(minutes=20), name="NotesJob")
    async def card(self, context: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行自动便签提醒")
        await self.daily_note_system.do_get_notes_job(context)
        logger.success("执行自动便签提醒完成")
