import asyncio
from asyncio import Lock
from copy import deepcopy
from datetime import datetime
from typing import ParamSpec, TYPE_CHECKING, TypeVar

import aiofiles
import pydantic
from simnet import GenshinClient
from simnet.errors import BadRequest as SimnetBadRequest
from simnet.errors import InvalidCookies
from telegram.constants import ChatAction, ParseMode

from core.dependence.assets import AssetsService
from gram_core.plugin import Plugin, handler
from gram_core.services.template.models import FileType, RenderGroupResult
from gram_core.services.template.services import TemplateService
from plugins.genshin.farming._const import AREAS
from plugins.genshin.farming._model import AreaData, AvatarData, FullFarmingData, RenderData, UserOwned, WeaponData
from plugins.genshin.farming._spider import Spider
from plugins.tools.genshin import CharacterDetails, CookiesNotFoundError, GenshinHelper, PlayerNotFoundError
from utils.const import DATA_DIR
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from telegram import Message, Update
    from telegram.ext import ContextTypes

R = TypeVar("R")
P = ParamSpec("P")

_RETRY_TIMES = 5
_WEEK_MAP = ["一", "二", "三", "四", "五", "六", "日"]

DATA_FILE_PATH = DATA_DIR.joinpath("daily_material.json").resolve()


def sort_item(item: AvatarData | WeaponData) -> tuple:
    rarity = item.rarity
    level = item.level
    if isinstance(item, AvatarData):
        owned = item.constellation is not None
        strengthening = item.constellation or 0
    else:
        owned = item.refinement is not None
        strengthening = item.refinement or 0
    return owned, rarity, level, strengthening


class DailyFarming(Plugin):
    lock: Lock = Lock()

    full_farming_data = FullFarmingData()

    def __init__(
        self,
        assets: AssetsService,
        template: TemplateService,
        genshin_helper: GenshinHelper,
        character_details: CharacterDetails,
    ) -> None:
        self.assets_service = assets
        self.template_service = template
        self.helper = genshin_helper
        self.character_details = character_details

    async def _refresh_farming_data(self) -> bool:
        async with self.lock:
            if (result := await Spider.execute(self.assets_service)) is not None:
                self.full_farming_data.__root__ = result
            else:
                return False

        if self.full_farming_data:
            async with aiofiles.open(DATA_FILE_PATH, "w", encoding="utf-8") as file:
                await file.write(self.full_farming_data.json(ensure_ascii=False))
        return True

    # noinspection PyUnresolvedReferences
    async def initialize(self) -> None:
        """插件在初始化时，会检查一下本地是否缓存了每日素材的数据"""

        async def refresh_task():
            """构建每日素材文件的后台任务"""
            logger.info("开始获取并缓存每日素材表")
            if await self._refresh_farming_data():
                logger.success("每日素材表缓存成功")
            else:
                logger.error("每日素材表缓存失败，请稍后重试")

        # 当缓存不存在或已过期（默认 1 天）则重新下载
        if not await aiofiles.os.path.exists(DATA_FILE_PATH):
            # 由于构建后台任务的话错误不会输出并堵塞主线程，所以用前台任务
            await refresh_task()
        else:
            mtime = await aiofiles.os.path.getmtime(DATA_FILE_PATH)
            mtime = datetime.fromtimestamp(mtime)
            elapsed = datetime.now() - mtime
            if elapsed.days > 1:
                await refresh_task()

        # 若存在则直接使用
        if await aiofiles.os.path.exists(DATA_FILE_PATH):
            try:
                async with aiofiles.open(DATA_FILE_PATH, "rb") as file:
                    self.full_farming_data = FullFarmingData.parse_raw(await file.read())
            except pydantic.ValidationError:
                await aiofiles.os.remove(DATA_FILE_PATH)
                await refresh_task()

    async def _get_character_skill(self, client, character) -> list[int]:
        if getattr(client, "damaged", False):
            return []
        try:
            detail = await self.character_details.get_character_details(client, character)
            return [t.level for t in detail.talents if t.type in ["attack", "skill", "burst"]]
        except InvalidCookies:
            setattr(client, "damaged", True)
        except SimnetBadRequest as e:
            if e.ret_code == -502002:
                client.damaged = True
            setattr(client, "damaged", True)
        return []

    async def _get_user_items(self, user_id: int) -> tuple[GenshinClient | None, UserOwned]:
        """获取已经绑定的账号的角色、武器信息"""
        user_data = UserOwned()
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await self.helper.get_genshin_client(user_id)
            logger.debug("获取账号数据成功: UID=%s", client.player_id)

            characters = await client.get_genshin_characters(client.player_id)
            for character in filter(lambda x: x.name != "旅行者", characters):
                character_id = str(character.id)
                character_assets = self.assets_service.avatar(character_id)
                character_icon = await character_assets.icon(False)
                character_side = await character_assets.side(False)
                user_data.avatars[character_id] = AvatarData(
                    id=character_id,
                    name=character.name,
                    rarity=character.rarity,
                    icon=character_icon.as_uri(),
                    level=character.level,
                    constellation=character.constellation,
                    skills=await self._get_character_skill(client, character),
                )

                # 判定武器的突破次数是否大于 2, 若是, 则将图标替换为 awakened (觉醒) 的图标
                weapon = character.weapon
                if weapon.rarity < 4:
                    continue  # 忽略 4 星以下的武器
                weapon_id = str(weapon.id)
                weapon_icon_type = "icon" if weapon.ascension < 2 else "awaken"
                weapon_icon = await getattr(self.assets_service.weapon(weapon_id), weapon_icon_type)()
                if weapon_id not in user_data.weapons:
                    # 由于用户可能持有多把同一种武器
                    # 这里需要使用 List 来储存所有不同角色持有的同名武器
                    user_data.weapons[weapon_id] = []
                user_data.weapons[weapon_id].append(
                    WeaponData(
                        id=weapon_id,
                        name=weapon.name,
                        rarity=weapon.rarity,
                        icon=weapon_icon.as_uri(),
                        level=weapon.level,
                        refinement=weapon.refinement,
                        avatar_icon=character_side.as_uri(),
                    )
                )
        except (PlayerNotFoundError, CookiesNotFoundError):
            self.log_user(user_id, logger.info, "未查询到绑定的账号信息")
        except InvalidCookies:
            self.log_user(user_id, logger.info, "所绑定的账号信息已失效")
        else:
            # 没有异常返回数据
            return client, user_data
        # 有上述异常的， client 会返回 None
        return None, user_data

    async def _get_render_data(self, user_id, weekday, title, time_text):
        # 尝试获取用户已绑定的原神账号信息
        client, user_owned = await self._get_user_items(user_id)
        today_farming = self.full_farming_data.weekday(weekday)

        area_avatars: list[AreaData] = []
        area_weapons: list[AreaData] = []
        for area_data in today_farming.areas:
            items = []

            new_area_data = deepcopy(area_data)
            for avatar in area_data.avatars:
                items.append(user_owned.avatars.get(str(avatar.id), avatar))
            new_area_data.avatars = list(sorted(items, key=sort_item, reverse=True))

            for weapon in area_data.weapons:
                if weapons := user_owned.weapons.get(str(weapon.id), []):
                    items.extend(weapons)
                else:
                    items.append(weapon)
            new_area_data.weapons = list(sorted(items, key=sort_item, reverse=True))

            [area_weapons, area_avatars][bool(area_data.avatars)].append(new_area_data)

        return RenderData(
            title=title,
            time=time_text,
            uid=mask_number(client.player_id) if client else client,
            character=list(sorted(area_avatars, key=lambda x: AREAS.index(x.name))),
            weapon=list(sorted(area_weapons, key=lambda x: AREAS.index(x.name))),
        )

    @handler.command("daily_farming", block=False)
    async def daily_farming(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        """每日素材表

        使用方式： /daily_farming (星期)
        """
        user_id = await self.get_real_user_id(update)
        message: "Message" = update.effective_message
        args = self.get_args(context)

        weekday, title, time_text, full = _parse_time(args)

        self.log_user(update, logger.info, "每日素材命令请求 || 参数 weekday=%s full=%s", _WEEK_MAP[weekday - 1], full)

        if weekday == 7:
            from telegram.constants import ParseMode

            the_day = "今天" if title == "今日" else "这天"
            await message.reply_text(f"{the_day}是星期天, <b>全部素材都可以</b>刷哦~", parse_mode=ParseMode.HTML)
            return

        if self.lock.locked():  # 若检测到了第一个锁：正在下载每日素材表的数据
            loading_prompt = await message.reply_text("派蒙正在摘抄每日素材表，以后再来探索吧~")
            self.add_delete_message_job(loading_prompt, delay=5)
            return

        loading_prompt = await message.reply_text("派蒙可能需要找找图标素材，还请耐心等待哦~")
        await message.reply_chat_action(ChatAction.TYPING)

        # 获取已经缓存的秘境素材信息
        if not self.full_farming_data:  # 若没有缓存每日素材表的数据
            logger.info("正在获取每日素材缓存")
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            await self._refresh_farming_data()

        render_data = await self._get_render_data(user_id, weekday, title, time_text)

        await message.reply_chat_action(ChatAction.TYPING)

        # 是否发送原图
        file_type = FileType.DOCUMENT if full else FileType.PHOTO

        character_img_data, weapon_img_data = await asyncio.gather(
            self.template_service.render(  # 渲染角色素材页
                "genshin/daily_farming/character.jinja2",
                {"data": render_data},
                {"width": 1338, "height": 500},
                file_type=file_type,
                ttl=30 * 24 * 60 * 60,
            ),
            self.template_service.render(  # 渲染武器素材页
                "genshin/daily_farming/weapon.jinja2",
                {"data": render_data},
                {"width": 1338, "height": 500},
                file_type=file_type,
                ttl=30 * 24 * 60 * 60,
            ),
        )

        self.add_delete_message_job(loading_prompt, delay=5)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        character_img_data.filename = f"{title}可培养角色.png"
        weapon_img_data.filename = f"{title}可培养武器.png"

        await RenderGroupResult([character_img_data, weapon_img_data]).reply_media_group(message)

        logger.debug("角色、武器培养素材图发送成功")

    @handler.command("refresh_farming_data", admin=True, block=False)
    async def refresh_farming_data(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        message = update.effective_message

        logger.info("用户 {%s}[%s] 刷新[bold]每日素材[/]缓存命令", user.full_name, user.id, extra={"markup": True})
        if self.lock.locked():
            notice = await message.reply_text("派蒙还在抄每日素材表呢，我有在好好工作哦~")
            self.add_delete_message_job(notice, delay=10)
            return

        notice = await message.reply_text("派蒙正在重新摘抄每日素材表，请稍等~", parse_mode=ParseMode.HTML)
        async with self.lock:  # 锁住第一把锁
            await self._refresh_farming_data()
        await notice.edit_text(
            "每日素材表"
            + ("摘抄<b>完成！</b>" if self.full_farming_data else "坏掉了！等会它再长好了之后我再抄。。。"),
            parse_mode=ParseMode.HTML,
        )


def _parse_time(args: list[str]) -> tuple[int, str, str, bool]:
    now = datetime.now()

    try:
        weekday = (_ := int(args[0])) - (_ > 0)
        weekday = (weekday % 7 + 7) % 7
        time_text = title = f"星期{_WEEK_MAP[weekday]}"
    except (ValueError, IndexError):
        title = "今日"
        weekday = now.weekday() - (1 if now.hour < 4 else 0)
        weekday = 6 if weekday < 0 else weekday
        time_text = f"星期{_WEEK_MAP[weekday]}"

    full = bool(args and args[-1] == "full")

    return weekday + 1, title, time_text, full
