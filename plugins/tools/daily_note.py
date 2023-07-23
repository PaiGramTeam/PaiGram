import base64
from typing import TYPE_CHECKING, List, Optional, Dict

from pydantic import BaseModel, validator
from simnet.errors import BadRequest as SimnetBadRequest, InvalidCookies, TimedOut as SimnetTimedOut
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

from core.basemodel import RegionEnum
from core.plugin import Plugin
from core.services.task.models import Task as TaskUser, TaskStatusEnum
from core.services.task.services import TaskResinServices, TaskRealmServices, TaskExpeditionServices
from plugins.tools.genshin import GenshinHelper, PlayerNotFoundError, CookiesNotFoundError
from utils.log import logger

if TYPE_CHECKING:
    from simnet import GenshinClient
    from telegram.ext import ContextTypes


class TaskDataBase(BaseModel):
    noticed: Optional[bool] = False


class ResinData(TaskDataBase):
    notice_num: Optional[int] = 140

    @validator("notice_num")
    def notice_num_validator(cls, v):
        if v < 100 or v > 160:
            raise ValueError("树脂提醒数值必须在 100 ~ 160 之间")
        return v


class RealmData(TaskDataBase):
    notice_num: Optional[int] = 2000

    @validator("notice_num")
    def notice_num_validator(cls, v):
        if v < 100 or v > 2400:
            raise ValueError("洞天宝钱提醒数值必须在 100 ~ 2400 之间")
        return v


class ExpeditionData(TaskDataBase):
    pass


class WebAppData(BaseModel):
    resin: Optional[ResinData]
    realm: Optional[RealmData]
    expedition: Optional[ExpeditionData]


class DailyNoteTaskUser:
    def __init__(
        self,
        user_id: int,
        resin_db: Optional[TaskUser] = None,
        realm_db: Optional[TaskUser] = None,
        expedition_db: Optional[TaskUser] = None,
    ):
        self.user_id = user_id
        self.resin_db = resin_db
        self.realm_db = realm_db
        self.expedition_db = expedition_db
        self.resin = ResinData(**self.resin_db.data) if self.resin_db else None
        self.realm = RealmData(**self.realm_db.data) if self.realm_db else None
        self.expedition = ExpeditionData(**self.expedition_db.data) if self.expedition_db else None

    @property
    def status(self) -> TaskStatusEnum:
        return max(
            [
                self.resin_db.status if self.resin_db else TaskStatusEnum.STATUS_SUCCESS,
                self.realm_db.status if self.realm_db else TaskStatusEnum.STATUS_SUCCESS,
                self.expedition_db.status if self.expedition_db else TaskStatusEnum.STATUS_SUCCESS,
            ]
        )

    @status.setter
    def status(self, value: TaskStatusEnum):
        if self.resin_db:
            self.resin_db.status = value
        if self.realm_db:
            self.realm_db.status = value
        if self.expedition_db:
            self.expedition_db.status = value

    @staticmethod
    def js_bool(value: bool) -> str:
        return "true" if value else "false"

    @staticmethod
    def set_model_noticed(model: TaskDataBase):
        data = model.copy(deep=True)
        data.noticed = True
        return data

    @property
    def web_config(self) -> str:
        return base64.b64encode(
            (
                WebAppData(
                    resin=self.set_model_noticed(self.resin) if self.resin else None,
                    realm=self.set_model_noticed(self.realm) if self.realm else None,
                    expedition=self.set_model_noticed(self.expedition) if self.expedition else None,
                ).json()
            ).encode()
        ).decode()

    def save(self):
        if self.resin_db:
            self.resin_db.data = self.resin.dict()
        if self.realm_db:
            self.realm_db.data = self.realm.dict()
        if self.expedition_db:
            self.expedition_db.data = self.expedition.dict()


class DailyNoteSystem(Plugin):
    def __init__(
        self,
        genshin_helper: GenshinHelper,
        resin_service: TaskResinServices,
        realm_service: TaskRealmServices,
        expedition_service: TaskExpeditionServices,
    ):
        self.genshin_helper = genshin_helper
        self.resin_service = resin_service
        self.realm_service = realm_service
        self.expedition_service = expedition_service

    async def get_single_task_user(self, user_id: int) -> DailyNoteTaskUser:
        resin_db = await self.resin_service.get_by_user_id(user_id)
        realm_db = await self.realm_service.get_by_user_id(user_id)
        expedition_db = await self.expedition_service.get_by_user_id(user_id)
        return DailyNoteTaskUser(
            user_id=user_id,
            resin_db=resin_db,
            realm_db=realm_db,
            expedition_db=expedition_db,
        )

    @staticmethod
    async def start_get_notes(
        client: "GenshinClient",
        user: DailyNoteTaskUser = None,
    ) -> List[str]:
        if client.region == RegionEnum.HOYOLAB:
            notes = await client.get_genshin_notes()
        else:
            notes = await client.get_genshin_notes_by_stoken()
        if not user:
            return []
        notices = []
        notice = None
        if user.resin_db and notes.max_resin > 0:
            if notes.current_resin >= user.resin.notice_num:
                if not user.resin.noticed:
                    notice = (
                        f"### 树脂提示 ####\n\n当前树脂为 {notes.current_resin} / {notes.max_resin} ，记得使用哦~\n"
                        f"预计全部恢复完成：{notes.resin_recovery_time.strftime('%Y-%m-%d %H:%M')}"
                    )
                    user.resin.noticed = True
            else:
                user.resin.noticed = False
        notices.append(notice)
        notice = None
        if user.realm_db and notes.max_realm_currency > 0:
            if notes.current_realm_currency >= user.realm.notice_num:
                if not user.realm.noticed:
                    notice = (
                        f"### 洞天宝钱提示 ####\n\n"
                        f"当前存储为 {notes.current_realm_currency} / {notes.max_realm_currency} ，记得领取哦~"
                    )
                    user.realm.noticed = True
            else:
                user.realm.noticed = False
        notices.append(notice)
        notice = None
        if user.expedition_db and len(notes.expeditions) > 0:
            all_finished = all(i.status == "Finished" for i in notes.expeditions)
            if all_finished:
                if not user.expedition.noticed:
                    notice = "### 探索派遣提示 ####\n\n所有探索派遣已完成，记得重新派遣哦~"
                    user.expedition.noticed = True
            else:
                user.expedition.noticed = False
        notices.append(notice)
        user.save()
        return notices

    async def get_all_task_users(self) -> List[DailyNoteTaskUser]:
        resin_list = await self.resin_service.get_all()
        realm_list = await self.realm_service.get_all()
        expedition_list = await self.expedition_service.get_all()
        user_list = set()
        for i in resin_list:
            user_list.add(i.user_id)
        for i in realm_list:
            user_list.add(i.user_id)
        for i in expedition_list:
            user_list.add(i.user_id)
        return [
            DailyNoteTaskUser(
                user_id=i,
                resin_db=next((x for x in resin_list if x.user_id == i), None),
                realm_db=next((x for x in realm_list if x.user_id == i), None),
                expedition_db=next((x for x in expedition_list if x.user_id == i), None),
            )
            for i in user_list
        ]

    async def remove_task_user(self, user: DailyNoteTaskUser):
        if user.resin_db:
            await self.resin_service.remove(user.resin_db)
        if user.realm_db:
            await self.realm_service.remove(user.realm_db)
        if user.expedition_db:
            await self.expedition_service.remove(user.expedition_db)

    async def update_task_user(self, user: DailyNoteTaskUser):
        if user.resin_db:
            await self.resin_service.update(user.resin_db)
        if user.realm_db:
            await self.realm_service.update(user.realm_db)
        if user.expedition_db:
            await self.expedition_service.update(user.expedition_db)

    @staticmethod
    async def check_need_note(web_config: WebAppData) -> bool:
        need_verify = False
        if web_config.resin:
            if web_config.resin.noticed:
                need_verify = True
        if web_config.realm:
            if web_config.realm.noticed:
                need_verify = True
        if web_config.expedition:
            if web_config.expedition.noticed:
                need_verify = True
        return need_verify

    async def import_web_config(self, user_id: int, web_config: WebAppData):
        user = await self.get_single_task_user(user_id)
        if web_config.resin:
            if web_config.resin.noticed:
                if not user.resin_db:
                    resin = self.resin_service.create(
                        user_id,
                        user_id,
                        status=TaskStatusEnum.STATUS_SUCCESS,
                        data=ResinData(notice_num=web_config.resin.notice_num).dict(),
                    )
                    await self.resin_service.add(resin)
                else:
                    user.resin.notice_num = web_config.resin.notice_num
                    user.resin.noticed = False
            else:
                if user.resin_db:
                    await self.resin_service.remove(user.resin_db)
                    user.resin_db = None
                    user.resin = None
        if web_config.realm:
            if web_config.realm.noticed:
                if not user.realm_db:
                    realm = self.realm_service.create(
                        user_id,
                        user_id,
                        status=TaskStatusEnum.STATUS_SUCCESS,
                        data=RealmData(notice_num=web_config.realm.notice_num).dict(),
                    )
                    await self.realm_service.add(realm)
                else:
                    user.realm.notice_num = web_config.realm.notice_num
                    user.realm.noticed = False
            else:
                if user.realm_db:
                    await self.realm_service.remove(user.realm_db)
                    user.realm_db = None
                    user.realm = None
        if web_config.expedition:
            if web_config.expedition.noticed:
                if not user.expedition_db:
                    expedition = self.expedition_service.create(
                        user_id,
                        user_id,
                        status=TaskStatusEnum.STATUS_SUCCESS,
                        data=ExpeditionData().dict(),
                    )
                    await self.expedition_service.add(expedition)
                else:
                    user.expedition.noticed = False
            else:
                if user.expedition_db:
                    await self.expedition_service.remove(user.expedition_db)
                    user.expedition_db = None
                    user.expedition = None
        user.save()
        await self.update_task_user(user)

    async def do_get_notes_job(self, context: "ContextTypes.DEFAULT_TYPE"):
        include_status: List[TaskStatusEnum] = [
            TaskStatusEnum.STATUS_SUCCESS,
            TaskStatusEnum.TIMEOUT_ERROR,
        ]
        task_list = await self.get_all_task_users()
        for task_db in task_list:
            if task_db.status not in include_status:
                continue
            user_id = task_db.user_id
            try:
                async with self.genshin_helper.genshin(user_id) as client:
                    text = await self.start_get_notes(client, task_db)
                if all(not i for i in text):
                    continue
            except InvalidCookies:
                text = "自动便签提醒执行失败，Cookie无效"
                task_db.status = TaskStatusEnum.INVALID_COOKIES
            except SimnetBadRequest as exc:
                text = f"自动便签提醒执行失败，API返回信息为 {str(exc)}"
                task_db.status = TaskStatusEnum.GENSHIN_EXCEPTION
            except SimnetTimedOut:
                text = "便签获取失败了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ "
                task_db.status = TaskStatusEnum.TIMEOUT_ERROR
            except PlayerNotFoundError:
                logger.info("用户 user_id[%s] 玩家不存在 关闭并移除自动便签提醒", user_id)
                await self.remove_task_user(task_db)
                continue
            except CookiesNotFoundError:
                logger.info("用户 user_id[%s] cookie 不存在 关闭并移除自动便签提醒", user_id)
                await self.remove_task_user(task_db)
                continue
            except Exception as exc:
                logger.error("执行自动便签提醒时发生错误 user_id[%s]", user_id, exc_info=exc)
                text = "获取便签失败了呜呜呜 ~ 执行自动便签提醒时发生错误"
            else:
                task_db.status = TaskStatusEnum.STATUS_SUCCESS
            for idx, task_user_db in enumerate([task_db.resin_db, task_db.realm_db, task_db.expedition_db]):
                if task_user_db is None:
                    continue
                notice_text = text[idx] if isinstance(text, list) else text
                if not notice_text:
                    continue
                if task_user_db.chat_id < 0:
                    notice_text = f'<a href="tg://user?id={task_user_db.user_id}">NOTICE {task_user_db.user_id}</a>\n\n{notice_text}'
                try:
                    await context.bot.send_message(task_user_db.chat_id, notice_text, parse_mode=ParseMode.HTML)
                except BadRequest as exc:
                    logger.error("执行自动便签提醒时发生错误 user_id[%s] Message[%s]", user_id, exc.message)
                    task_user_db.status = TaskStatusEnum.BAD_REQUEST
                except Forbidden as exc:
                    logger.error("执行自动便签提醒时发生错误 user_id[%s] message[%s]", user_id, exc.message)
                    task_user_db.status = TaskStatusEnum.FORBIDDEN
                except Exception as exc:
                    logger.error("执行自动便签提醒时发生错误 user_id[%s]", user_id, exc_info=exc)
                    continue
                else:
                    task_user_db.status = TaskStatusEnum.STATUS_SUCCESS
            await self.update_task_user(task_db)
