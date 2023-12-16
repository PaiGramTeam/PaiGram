from functools import partial
from typing import Dict, List, TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.plugin import Plugin, handler
from gram_core.plugin.methods.migrate_data import IMigrateData, MigrateDataException
from gram_core.services.players import PlayersService
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class MigrateAdmin(Plugin):
    def __init__(self, players_service: PlayersService):
        self.players_service = players_service
        self.cache_data: Dict[int, List[IMigrateData]] = {}
        self.wait_time = 60

    async def _add_pop_cache_job(self, user_id: int) -> None:
        if user_id in self.cache_data:
            del self.cache_data[user_id]

    def add_pop_cache_job(self, user_id: int) -> None:
        job_queue = self.application.job_queue
        if job_queue is None:
            raise RuntimeError
        job_queue.run_once(
            callback=partial(self._add_pop_cache_job, user_id=user_id), when=60, name=f"{user_id}|migrate_pop_cache"
        )

    def cancel_pop_cache_job(self, user_id: int) -> None:
        job_queue = self.application.job_queue
        if job_queue is None:
            raise RuntimeError
        if job := job_queue.get_jobs_by_name(f"{user_id}|migrate_pop_cache"):
            job[0].schedule_removal()

    @handler.command(command="migrate_admin", block=False, admin=True)
    async def migrate_admin_command(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        args = self.get_args(context)
        logger.info("管理员 %s[%s] migrate_admin 命令请求", message.from_user.full_name, message.from_user.id)
        if (not args) or len(args) < 2:
            await message.reply_text("参数错误，请指定新旧用户 id ！")
            return
        try:
            old_user_id, new_user_id = int(args[0]), int(args[1])
        except ValueError:
            await message.reply_text("参数错误，请指定新旧用户 id ！")
            return
        if old_user_id in self.cache_data:
            await message.reply_text("该用户正在迁移数据中，请稍后再试！")
            return
        data = []
        players = await self.players_service.get_all_by_user_id(old_user_id)
        for _, instance in self.application.managers.plugins_map.items():
            if _data := await instance.get_migrate_data(old_user_id, new_user_id, players):
                data.append(_data)
        if not data:
            await message.reply_text("没有需要迁移的数据！")
            return
        text = "确定迁移以下数据？\n\n"
        for d in data:
            text += f"- {await d.migrate_data_msg()}\n"
        self.cache_data[old_user_id] = data
        buttons = [
            [
                InlineKeyboardButton(
                    "确定迁移",
                    callback_data=f"migrate_admin|{old_user_id}",
                )
            ],
        ]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        self.add_pop_cache_job(old_user_id)

    async def try_migrate_data(self, user_id: int) -> str:
        text = []
        for d in self.cache_data[user_id]:
            try:
                logger.info("开始迁移数据 class[%s]", d.__class__.__name__)
                await d.migrate_data()
                logger.info("迁移数据成功 class[%s]", d.__class__.__name__)
            except MigrateDataException as e:
                text.append(e.msg)
            except Exception as e:
                logger.exception("迁移数据失败，未知错误！ class[%s]", d.__class__.__name__, exc_info=e)
                text.append("迁移部分数据出现未知错误，请联系管理员！")
        if text:
            return "- " + "\n- ".join(text)

    @handler.callback_query(pattern=r"^migrate_admin\|", block=False)
    async def callback_query_migrate_admin(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message
        logger.info("管理员 %s[%s] migrate_admin callback 请求", user.full_name, user.id)

        async def get_migrate_admin_callback(callback_query_data: str) -> int:
            _data = callback_query_data.split("|")
            _old_user_id = int(_data[1])
            logger.debug("callback_query_data函数返回 old_user_id[%s]", _old_user_id)
            return _old_user_id

        old_user_id = await get_migrate_admin_callback(callback_query.data)
        if old_user_id not in self.cache_data:
            await callback_query.answer("请求已过期，请重新发起请求！", show_alert=True)
            self.add_delete_message_job(message, delay=5)
            return
        self.cancel_pop_cache_job(old_user_id)
        await message.edit_text("正在迁移数据，请稍后...", reply_markup=None)
        try:
            text = await self.try_migrate_data(old_user_id)
        finally:
            await self._add_pop_cache_job(old_user_id)
        if text:
            await message.edit_text(f"迁移部分数据失败！\n\n{text}")
            return
        await message.edit_text("迁移数据成功！")
