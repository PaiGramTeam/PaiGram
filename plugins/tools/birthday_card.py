from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from simnet.errors import BadRequest as SimnetBadRequest, RegionNotSupported, InvalidCookies, TimedOut as SimnetTimedOut
from simnet.client.routes import Route
from simnet.utils.player import recognize_genshin_game_biz, recognize_genshin_server
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

from core.basemodel import RegionEnum
from core.plugin import Plugin
from core.services.task.models import TaskStatusEnum
from core.services.task.services import TaskCardServices
from metadata.shortname import roleToId
from modules.apihelper.client.components.calendar import Calendar
from plugins.tools.genshin import GenshinHelper, PlayerNotFoundError, CookiesNotFoundError
from utils.log import logger

if TYPE_CHECKING:
    from simnet import GenshinClient
    from telegram.ext import ContextTypes

BIRTHDAY_URL = Route(
    "https://hk4e-api.mihoyo.com/event/birthdaystar/account/post_my_draw",
)


def rm_starting_str(string, starting):
    """Remove the starting character from a string."""
    while string[0] == str(starting):
        string = string[1:]
    return string


class BirthdayCardNoBirthdayError(Exception):
    pass


class BirthdayCardAlreadyClaimedError(Exception):
    pass


class BirthdayCardSystem(Plugin):
    def __init__(
        self,
        card_service: TaskCardServices,
        genshin_helper: GenshinHelper,
    ):
        self.birthday_list = {}
        self.card_service = card_service
        self.genshin_helper = genshin_helper

    async def initialize(self):
        self.birthday_list = await Calendar.async_gen_birthday_list()
        self.birthday_list.get("6_1", []).append("派蒙")

    @property
    def key(self):
        return (
            rm_starting_str(datetime.now().strftime("%m"), "0")
            + "_"
            + rm_starting_str(datetime.now().strftime("%d"), "0")
        )

    def get_today_birthday(self) -> List[str]:
        key = self.key
        return (self.birthday_list.get(key, [])).copy()

    @staticmethod
    def role_to_id(name: str) -> Optional[int]:
        if name == "派蒙":
            return -1
        return roleToId(name)

    @staticmethod
    async def get_card(client: "GenshinClient", role_id: int) -> None:
        """领取画片"""
        url = BIRTHDAY_URL.get_url()
        params = {
            "game_biz": recognize_genshin_game_biz(client.player_id),
            "lang": "zh-cn",
            "badge_uid": client.player_id,
            "badge_region": recognize_genshin_server(client.player_id),
            "activity_id": "20220301153521",
        }
        json = {
            "role_id": role_id,
        }
        try:
            await client.request_lab(url, method="POST", params=params, data=json)
        except SimnetBadRequest as e:
            if e.retcode == -512008:
                raise BirthdayCardNoBirthdayError from e  # 未过生日
            if e.retcode == -512009:
                raise BirthdayCardAlreadyClaimedError from e  # 已领取过
            raise e

    async def start_get_card(
        self,
        client: "GenshinClient",
    ) -> str:
        if client.region == RegionEnum.HOYOLAB:
            raise RegionNotSupported
        today_list = self.get_today_birthday()
        if not today_list:
            raise BirthdayCardNoBirthdayError
        game_biz = recognize_genshin_game_biz(client.player_id)
        region = recognize_genshin_server(client.player_id)
        await client.get_hk4e_token_by_cookie_token(game_biz, region)
        for name in today_list.copy():
            if role_id := self.role_to_id(name):
                try:
                    await self.get_card(client, role_id)
                except BirthdayCardAlreadyClaimedError:
                    today_list.remove(name)
        if today_list:
            text = f"成功领取了 {'、'.join(today_list)} 的生日画片~"
        else:
            raise BirthdayCardAlreadyClaimedError
        return text

    async def do_get_card_job(self, context: "ContextTypes.DEFAULT_TYPE"):
        if not self.get_today_birthday():
            logger.info("今天没有角色过生日，跳过自动领取生日画片")
            return
        include_status: List[TaskStatusEnum] = [
            TaskStatusEnum.STATUS_SUCCESS,
            TaskStatusEnum.TIMEOUT_ERROR,
        ]
        task_list = await self.card_service.get_all()
        for task_db in task_list:
            if task_db.status not in include_status:
                continue
            user_id = task_db.user_id
            try:
                async with self.genshin_helper.genshin(user_id) as client:
                    text = await self.start_get_card(client)
            except InvalidCookies:
                text = "自动领取生日画片执行失败，Cookie无效"
                task_db.status = TaskStatusEnum.INVALID_COOKIES
            except BirthdayCardAlreadyClaimedError:
                text = "今天旅行者已经领取过了~"
                task_db.status = TaskStatusEnum.ALREADY_CLAIMED
            except SimnetBadRequest as exc:
                text = f"自动领取生日画片执行失败，API返回信息为 {str(exc)}"
                task_db.status = TaskStatusEnum.GENSHIN_EXCEPTION
            except SimnetTimedOut:
                text = "领取失败了呜呜呜 ~ 服务器连接超时 服务器熟啦 ~ "
                task_db.status = TaskStatusEnum.TIMEOUT_ERROR
            except PlayerNotFoundError:
                logger.info("用户 user_id[%s] 玩家不存在 关闭并移除自动领取生日画片", user_id)
                await self.card_service.remove(task_db)
                continue
            except CookiesNotFoundError:
                logger.info("用户 user_id[%s] cookie 不存在 关闭并移除自动领取生日画片", user_id)
                await self.card_service.remove(task_db)
                continue
            except RegionNotSupported:
                logger.info("用户 user_id[%s] 不支持的服务器 关闭并移除自动领取生日画片", user_id)
                await self.card_service.remove(task_db)
                continue
            except Exception as exc:
                logger.error("执行自动领取生日画片时发生错误 user_id[%s]", user_id, exc_info=exc)
                text = "自动领取生日画片失败了呜呜呜 ~ 执行自动领取生日画片时发生错误"
            else:
                task_db.status = TaskStatusEnum.STATUS_SUCCESS
            if task_db.chat_id < 0:
                text = f'<a href="tg://user?id={task_db.user_id}">NOTICE {task_db.user_id}</a>\n\n{text}'
            try:
                await context.bot.send_message(task_db.chat_id, text, parse_mode=ParseMode.HTML)
            except BadRequest as exc:
                logger.error("执行自动领取生日画片时发生错误 user_id[%s] Message[%s]", user_id, exc.message)
                task_db.status = TaskStatusEnum.BAD_REQUEST
            except Forbidden as exc:
                logger.error("执行自动领取生日画片时发生错误 user_id[%s] message[%s]", user_id, exc.message)
                task_db.status = TaskStatusEnum.FORBIDDEN
            except Exception as exc:
                logger.error("执行自动领取生日画片时发生错误 user_id[%s]", user_id, exc_info=exc)
                continue
            else:
                task_db.status = TaskStatusEnum.STATUS_SUCCESS
            await self.card_service.update(task_db)
