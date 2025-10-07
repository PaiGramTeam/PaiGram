import asyncio
import typing
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Iterable, Iterator, List, Optional, Tuple

from arkowrapper import ArkoWrapper
from httpx import AsyncClient
from pydantic import BaseModel
from simnet.errors import BadRequest as SimnetBadRequest
from simnet.errors import InvalidCookies
from simnet.models.base import add_timezone
from simnet.models.genshin.chronicle.characters import Character
from telegram.constants import ChatAction, ParseMode

from core.config import config
from core.dependence.assets.impl.genshin import AssetsCouldNotFound, AssetsService
from core.dependence.assets.impl.models.genshin.daily_material import MaterialsData, AreaDailyMaterialsData
from core.plugin import Plugin, handler
from core.services.template.models import FileType, RenderGroupResult
from core.services.template.services import TemplateService
from metadata.pool.pool_301 import POOL_301 as CHARACTER_POOL
from modules.gacha_log.models import Pool
from plugins.tools.genshin import CharacterDetails, CookiesNotFoundError, GenshinHelper, PlayerNotFoundError
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from simnet import GenshinClient
    from telegram import Message, Update
    from telegram.ext import ContextTypes

WEEK_MAP = ["一", "二", "三", "四", "五", "六", "日"]


def sort_item(items: List["ItemData"]) -> Iterable["ItemData"]:
    """对武器和角色进行排序

    排序规则：持有（星级 > 等级 > 命座/精炼) > 未持有（星级 > 等级 > 命座/精炼）
    """

    def key(item: "ItemData"):
        # 有个小小的意外逻辑，不影响排序输出，如果要修改可能需要注意下：
        # constellation 可以为 None 或 0，此时都会被判断为 False
        # 此时 refinment or constellation or -1 都会返回 -1
        # 但不影响排序结果
        return (
            item.level is not None,  # 根据持有与未持有进行分组并排序
            item.rarity,  # 根据星级分组并排序
            item.refinement or item.constellation or -1,  # 根据命座/精炼进行分组并排序
            item.id,  # 默认按照物品 ID 进行排序
        )

    return sorted(items, key=key, reverse=True)


def get_material_serial_name(names: Iterable[str]) -> str:
    """
    获取材料的系列名，本质上是求字符串列表的最长子串
    如：「自由」的教导、「自由」的指引、「自由」的哲学，三者系列名为「『自由』」
    如：高塔孤王的破瓦、高塔孤王的残垣、高塔孤王的断片、高塔孤王的碎梦，四者系列名为「高塔孤王」
    TODO(xr1s): 感觉可以优化
    """

    def all_substrings(string: str) -> Iterator[str]:
        """获取字符串的所有连续字串"""
        length = len(string)
        for i in range(length):
            for j in range(i + 1, length + 1):
                yield string[i:j]

    result = []
    for name_a, name_b in ArkoWrapper(names).repeat(1).group(2).unique(list):
        for sub_string in all_substrings(name_a):
            if sub_string in ArkoWrapper(all_substrings(name_b)):
                result.append(sub_string)
    result = ArkoWrapper(result).sort(len, reverse=True)[0]
    chars = {"的": 0, "之": 0}
    for char, k in chars.items():
        result = result.split(char)[k]
    return result


def is_first_week_of_pool(date: Optional["datetime"] = None) -> bool:
    target_date = date or datetime.now()
    target_date_cn = add_timezone(target_date)
    pool = [Pool(**i) for i in CHARACTER_POOL]
    for p in pool:
        start, end = p.start, p.start + timedelta(weeks=1)
        if start <= target_date_cn < end:
            return True
    return False


class DailyMaterial(Plugin):
    """每日素材表"""

    everyday_materials: "MaterialsData" = MaterialsData()
    """
    everyday_materials 储存的是一周中每天能刷的素材 ID
    按照如下形式组织
    ```python
    everyday_materials[周几][国家] = AreaDailyMaterialsData(
      avatar=[角色, 角色, ...],
      avatar_materials=[精通素材, 精通素材, 精通素材],
      weapon=[武器, 武器, ...]
      weapon_materials=[炼武素材, 炼武素材, 炼武素材, 炼武素材],
    )
    ```
    """

    def __init__(
        self,
        assets: AssetsService,
        template_service: TemplateService,
        helper: GenshinHelper,
        character_details: CharacterDetails,
    ):
        self.assets_service = assets
        self.template_service = template_service
        self.helper = helper
        self.character_details = character_details
        self.client = AsyncClient()

    async def initialize(self):
        """插件在初始化时，会检查一下本地是否缓存了每日素材的数据"""
        self.everyday_materials = self.everyday_materials.model_validate(self.assets_service.other.get_daily_material())

    async def _get_skills_data(self, client: "FragileGenshinClient", character: Character) -> Optional[List[int]]:
        if client.damaged:
            return None
        detail = None
        try:
            real_client = typing.cast("GenshinClient", client.client)
            detail = await self.character_details.get_character_details(real_client, character)
        except InvalidCookies:
            client.damaged = True
        except SimnetBadRequest as e:
            if e.ret_code == -502002:
                client.damaged = True
            raise
        if detail is None:
            return None
        talents = [t for t in detail.talents if t.type in ["attack", "skill", "burst"]]
        return [t.level for t in talents]

    async def _get_items_from_user(
        self, user_id: int, uid: int, offset: int
    ) -> Tuple[Optional["GenshinClient"], "UserOwned"]:
        """获取已经绑定的账号的角色、武器信息"""
        user_data = UserOwned()
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await self.helper.get_genshin_client(user_id, player_id=uid, offset=offset)
            logger.debug("获取账号数据成功: UID=%s", client.player_id)
            characters = await client.get_genshin_characters(client.player_id)
            for character in characters:
                if character.name == "旅行者":
                    continue
                character_id = str(character.id)
                character_icon = self.assets_service.avatar.icon(character_id)
                character_side = self.assets_service.avatar.side(character_id)
                user_data.avatar[character_id] = ItemData(
                    id=character_id,
                    name=typing.cast(str, character.name),
                    rarity=int(typing.cast(str, character.rarity)),
                    level=character.level,
                    constellation=character.constellation,
                    gid=character.id,
                    icon=character_icon.as_uri(),
                    origin=character,
                )
                # 判定武器的突破次数是否大于 2, 若是, 则将图标替换为 awakened (觉醒) 的图标
                weapon = character.weapon
                weapon_id = str(weapon.id)
                weapon_icon = (
                    self.assets_service.weapon.icon(weapon_id)
                    if weapon.ascension < 2
                    else self.assets_service.weapon.awaken(weapon_id)
                )
                if weapon_id not in user_data.weapon:
                    # 由于用户可能持有多把同一种武器
                    # 这里需要使用 List 来储存所有不同角色持有的同名武器
                    user_data.weapon[weapon_id] = []
                user_data.weapon[weapon_id].append(
                    ItemData(
                        id=weapon_id,
                        name=weapon.name,
                        level=weapon.level,
                        rarity=weapon.rarity,
                        refinement=weapon.refinement,
                        icon=weapon_icon.as_uri(),
                        c_path=character_side.as_uri(),
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

    async def area_user_weapon(
        self,
        area_name: str,
        user_owned: "UserOwned",
        area_daily: "AreaDailyMaterialsData",
        loading_prompt: "Message",
    ) -> Optional["AreaData"]:
        """
        area_user_weapon 通过从选定区域当日可突破的武器中查找用户持有的武器
        计算 /daily_material 返回的页面中该国下会出现的武器列表
        """
        weapon_items: List["ItemData"] = []
        for weapon_id in area_daily.weapon:
            weapons = user_owned.weapon.get(weapon_id)
            if weapons is None or len(weapons) == 0:
                weapon = await self._assemble_item_from_honey_data("weapon", weapon_id)
                if weapon is None:
                    continue
                weapons = [weapon]
            if weapons[0].rarity < 4:
                continue
            weapon_items.extend(weapons)
        if len(weapon_items) == 0:
            return None
        weapon_materials = await self.user_materials(area_daily.weapon_materials, loading_prompt)
        return AreaData(
            name=area_name,
            materials=weapon_materials,
            items=list(sort_item(weapon_items)),
            material_name=get_material_serial_name(map(lambda x: x.name, weapon_materials)),
        )

    async def area_user_avatar(
        self,
        area_name: str,
        user_owned: "UserOwned",
        area_daily: "AreaDailyMaterialsData",
        client: "FragileGenshinClient",
        loading_prompt: "Message",
    ) -> Optional["AreaData"]:
        """
        area_user_avatar 通过从选定区域当日可升级的角色技能中查找用户拥有的角色
        计算 /daily_material 返回的页面中该国下会出现的角色列表
        """
        avatar_items: List[ItemData] = []
        for avatar_id in area_daily.avatar:
            avatar = user_owned.avatar.get(avatar_id)
            avatar = avatar or await self._assemble_item_from_honey_data("avatar", avatar_id)
            if avatar is None:
                continue
            if avatar.origin is None:
                avatar_items.append(avatar)
                continue
            # 最大努力获取用户角色等级
            try:
                avatar.skills = await self._get_skills_data(client, avatar.origin)
            except SimnetBadRequest as e:
                if e.ret_code != -502002:
                    raise e
                self.add_delete_message_job(loading_prompt, delay=5)
                await loading_prompt.edit_text(
                    "获取角色天赋信息失败，如果想要显示角色天赋信息，请先在米游社/HoYoLab中使用一次<b>养成计算器</b>后再使用此功能~",
                    parse_mode=ParseMode.HTML,
                )
            avatar_items.append(avatar)
        if len(avatar_items) == 0:
            return None
        avatar_materials = await self.user_materials(area_daily.avatar_materials, loading_prompt)
        return AreaData(
            name=area_name,
            materials=avatar_materials,
            items=list(sort_item(avatar_items)),
            material_name=get_material_serial_name(map(lambda x: x.name, avatar_materials)),
        )

    async def user_materials(self, material_ids: List[str], loading_prompt: "Message") -> List["ItemData"]:
        """
        user_materials 返回 /daily_material 每个国家角色或武器列表右上角标的素材列表
        """
        area_materials: List[ItemData] = []
        for material_id in material_ids:  # 添加这个区域当天（weekday）的培养素材
            try:
                material_icon = self.assets_service.material.icon(material_id)
            except AssetsCouldNotFound as exc:
                logger.warning("AssetsCouldNotFound message[%s] target[%s]", exc.message, exc.target)
                await loading_prompt.edit_text(f"出错了呜呜呜 ~ {config.notice.bot_name}找不到一些素材")
                raise
            material = self.assets_service.material.get_by_name(material_id)
            material_uri = material_icon.as_uri()
            area_materials.append(
                ItemData(
                    id=material_id,
                    icon=material_uri,
                    name=material.name,
                    rarity=material.rank,
                )
            )
        return area_materials

    @handler.command("daily_material", block=False)
    async def daily_material(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = typing.cast("Message", update.effective_message)
        args = self.get_args(context)
        now = datetime.now()

        try:
            weekday = (_ := int(args[0])) - (_ > 0)
            weekday = (weekday % 7 + 7) % 7
            time = title = f"星期{WEEK_MAP[weekday]}"
        except (ValueError, IndexError):
            title = "今日"
            weekday = now.weekday() - (1 if now.hour < 4 else 0)
            weekday = 6 if weekday < 0 else weekday
            time = f"星期{WEEK_MAP[weekday]}"
        full = bool(args and args[-1] == "full")  # 判定最后一个参数是不是 full

        self.log_user(update, logger.info, "每日素材命令请求 || 参数 weekday=%s full=%s", WEEK_MAP[weekday], full)

        if weekday == 6:
            the_day = "今天" if title == "今日" else "这天"
            await message.reply_text(f"{the_day}是星期天, <b>全部素材都可以</b>刷哦~", parse_mode=ParseMode.HTML)
            return
        if title == "今日" and is_first_week_of_pool(now):
            await message.reply_text("今天属于卡池开放第一周，<b>全部素材都可以</b>刷哦~", parse_mode=ParseMode.HTML)
            return

        loading_prompt = await message.reply_text(f"{config.notice.bot_name}可能需要找找图标素材，还请耐心等待哦~")
        await message.reply_chat_action(ChatAction.TYPING)

        # 尝试获取用户已绑定的原神账号信息
        client, user_owned = await self._get_items_from_user(user_id, uid, offset)
        today_materials = self.everyday_materials.weekday(weekday)
        fragile_client = FragileGenshinClient(client)
        area_avatars: List["AreaData"] = []
        area_weapons: List["AreaData"] = []
        for country_name, area_daily in today_materials.items():
            area_avatar = await self.area_user_avatar(
                country_name, user_owned, area_daily, fragile_client, loading_prompt
            )
            if area_avatar is not None:
                area_avatars.append(area_avatar)
            area_weapon = await self.area_user_weapon(country_name, user_owned, area_daily, loading_prompt)
            if area_weapon is not None:
                area_weapons.append(area_weapon)
        render_data = RenderData(
            title=title,
            time=time,
            uid=mask_number(client.player_id) if client else client,
            character=area_avatars,
            weapon=area_weapons,
        )

        await message.reply_chat_action(ChatAction.TYPING)

        # 是否发送原图
        file_type = FileType.DOCUMENT if full else FileType.PHOTO

        character_img_data, weapon_img_data = await asyncio.gather(
            self.template_service.render(  # 渲染角色素材页
                "genshin/daily_material/character.jinja2",
                {"data": render_data},
                {"width": 2060, "height": 500},
                file_type=file_type,
                ttl=30 * 24 * 60 * 60,
            ),
            self.template_service.render(  # 渲染武器素材页
                "genshin/daily_material/weapon.jinja2",
                {"data": render_data},
                {"width": 2060, "height": 500},
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

    async def _assemble_item_from_honey_data(self, item_type: str, item_id: str) -> Optional["ItemData"]:
        """用户拥有的角色和武器中找不到数据时，使用 HoneyImpact 的数据组装出基本信息置灰展示"""
        honey_item = getattr(self.assets_service, item_type).get_by_id(item_id)
        if honey_item is None:
            return None
        try:
            icon = getattr(self.assets_service, item_type).icon(item_id)
        except KeyError:
            return None
        return ItemData(
            id=item_id,
            name=honey_item.name,
            rarity=honey_item.rank,
            icon=icon.as_uri(),
        )


class FragileGenshinClient:
    def __init__(self, client: Optional["GenshinClient"]):
        self.client = client
        self._damaged = False

    @property
    def damaged(self):
        return self._damaged or self.client is None

    @damaged.setter
    def damaged(self, damaged: bool):
        self._damaged = damaged


class ItemData(BaseModel):
    id: str  # ID
    name: str  # 名称
    rarity: int  # 星级
    icon: str  # 图标
    level: Optional[int] = None  # 等级
    constellation: Optional[int] = None  # 命座
    skills: Optional[List[int]] = None  # 天赋等级
    gid: Optional[int] = None  # 角色在 genshin.py 里的 ID
    refinement: Optional[int] = None  # 精炼度
    c_path: Optional[str] = None  # 武器使用者图标
    origin: Optional[Character] = None  # 原始数据


class AreaData(BaseModel):
    name: str  # 区域名
    material_name: str  # 区域的材料系列名
    materials: List[ItemData] = []  # 区域材料
    items: List[ItemData] = []  # 可培养的角色或武器


class RenderData(BaseModel):
    title: str  # 页面标题，主要用于显示星期几
    time: str  # 页面时间
    uid: Optional[str] = None  # 用户UID
    character: List[AreaData] = []  # 角色数据
    weapon: List[AreaData] = []  # 武器数据

    def __getitem__(self, item):
        return self.__getattribute__(item)


class UserOwned(BaseModel):
    avatar: Dict[str, ItemData] = {}
    """角色 ID 到角色对象的映射"""
    weapon: Dict[str, List[ItemData]] = {}
    """用户同时可以拥有多把同名武器，因此是 ID 到 List 的映射"""
