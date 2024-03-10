import asyncio
import typing
from asyncio import Lock
from ctypes import c_double
from datetime import datetime
from functools import partial
from multiprocessing import Value
from os import path
from ssl import SSLZeroReturnError
from time import time as time_
from typing import TYPE_CHECKING, Dict, Iterable, Iterator, List, Optional, Tuple

import aiofiles
import aiofiles.os
import bs4
import pydantic
from arkowrapper import ArkoWrapper
from httpx import AsyncClient, HTTPError, TimeoutException
from pydantic import BaseModel
from simnet.errors import BadRequest as SimnetBadRequest
from simnet.errors import InvalidCookies
from simnet.models.genshin.chronicle.characters import Character
from telegram.constants import ChatAction, ParseMode
from telegram.error import RetryAfter, TimedOut

from core.dependence.assets import AssetsCouldNotFound, AssetsService, AssetsServiceType
from core.plugin import Plugin, handler
from core.services.template.models import FileType, RenderGroupResult
from core.services.template.services import TemplateService
from metadata.genshin import AVATAR_DATA, HONEY_DATA
from plugins.tools.genshin import CharacterDetails, CookiesNotFoundError, GenshinHelper, PlayerNotFoundError
from utils.const import DATA_DIR
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from simnet import GenshinClient
    from telegram import Message, Update
    from telegram.ext import ContextTypes

INTERVAL = 1

DATA_FILE_PATH = DATA_DIR.joinpath("daily_material.json").resolve()
# fmt: off
# 章节顺序、国家（区域）名是从《足迹》 PV 中取的
DOMAINS = [
    "忘却之峡",      # 蒙德精通秘境
    "太山府",        # 璃月精通秘境
    "菫色之庭",      # 稻妻精通秘境
    "昏识塔",        # 须弥精通秘境
    "苍白的遗荣",    # 枫丹精通秘境
    "",              # 纳塔精通秘境
    "",              # 至东精通秘境
    "",              # 坎瑞亚精通秘境
    "塞西莉亚苗圃",  # 蒙德炼武秘境
    "震雷连山密宫",  # 璃月炼武秘境
    "砂流之庭",      # 稻妻炼武秘境
    "有顶塔",        # 须弥炼武秘境
    "深潮的余响",    # 枫丹炼武秘境
    "",              # 纳塔炼武秘境
    "",              # 至东炼武秘境
    "",              # 坎瑞亚炼武秘境
]
# fmt: on
DOMAIN_AREA_MAP = dict(zip(DOMAINS, ["蒙德", "璃月", "稻妻", "须弥", "枫丹", "纳塔", "至冬", "坎瑞亚"] * 2))
# 此处 avatar 和 weapon 需要分别对应 AreaDailyMaterialsData 中的两个 *_materials 字段，具体逻辑见 _parse_honey_impact_source
DOMAIN_TYPE_MAP = dict(zip(DOMAINS, len(DOMAINS) // 2 * ["avatar"] + len(DOMAINS) // 2 * ["weapon"]))

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


class MaterialsData(BaseModel):
    __root__: Optional[List[Dict[str, "AreaDailyMaterialsData"]]] = None

    def weekday(self, weekday: int) -> Dict[str, "AreaDailyMaterialsData"]:
        if self.__root__ is None:
            return {}
        return self.__root__[weekday]

    def is_empty(self) -> bool:
        return self.__root__ is None


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

    locks: Tuple[Lock, Lock] = (Lock(), Lock())
    """
    Tuple[每日素材缓存锁, 角色武器材料图标锁]
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

        async def task_daily():
            async with self.locks[0]:
                logger.info("正在开始获取每日素材缓存")
                await self._refresh_everyday_materials()

        # 当缓存不存在或已过期（大于 3 天）则重新下载
        # TODO(xr1s): 是不是可以改成 21 天？
        if not await aiofiles.os.path.exists(DATA_FILE_PATH):
            asyncio.create_task(task_daily())
        else:
            mtime = await aiofiles.os.path.getmtime(DATA_FILE_PATH)
            mtime = datetime.fromtimestamp(mtime)
            elapsed = datetime.now() - mtime
            if elapsed.days > 3:
                asyncio.create_task(task_daily())

        # 若存在则直接使用缓存
        if await aiofiles.os.path.exists(DATA_FILE_PATH):
            async with aiofiles.open(DATA_FILE_PATH, "rb") as cache:
                try:
                    self.everyday_materials.parse_raw(await cache.read())
                except pydantic.ValidationError:
                    await aiofiles.os.remove(DATA_FILE_PATH)
                    asyncio.create_task(task_daily())

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

    async def _get_items_from_user(self, user_id: int) -> Tuple[Optional["GenshinClient"], "UserOwned"]:
        """获取已经绑定的账号的角色、武器信息"""
        user_data = UserOwned()
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await self.helper.get_genshin_client(user_id)
            logger.debug("获取账号数据成功: UID=%s", client.player_id)
            characters = await client.get_genshin_characters(client.player_id)
            for character in characters:
                if character.name == "旅行者":
                    continue
                character_id = str(AVATAR_DATA[str(character.id)]["id"])
                character_assets = self.assets_service.avatar(character_id)
                character_icon = await character_assets.icon(False)
                character_side = await character_assets.side(False)
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
                weapon_awaken = "icon" if weapon.ascension < 2 else "awaken"
                weapon_icon = await getattr(self.assets_service.weapon(weapon_id), weapon_awaken)()
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
            material = None
            try:
                material = self.assets_service.material(material_id)
            except AssetsCouldNotFound as exc:
                logger.warning("AssetsCouldNotFound message[%s] target[%s]", exc.message, exc.target)
                await loading_prompt.edit_text("出错了呜呜呜 ~ 派蒙找不到一些素材")
                raise
            [_, material_name, material_rarity] = HONEY_DATA["material"][material_id]
            material_icon = await material.icon(False)
            material_uri = material_icon.as_uri()
            area_materials.append(
                ItemData(
                    id=material_id,
                    icon=material_uri,
                    name=typing.cast(str, material_name),
                    rarity=typing.cast(int, material_rarity),
                )
            )
        return area_materials

    @handler.command("daily_material", block=False)
    async def daily_material(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
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

        if self.locks[0].locked():  # 若检测到了第一个锁：正在下载每日素材表的数据
            loading_prompt = await message.reply_text("派蒙正在摘抄每日素材表，以后再来探索吧~")
            self.add_delete_message_job(loading_prompt, delay=5)
            return

        if self.locks[1].locked():  # 若检测到了第二个锁：正在下载角色、武器、材料的图标
            await message.reply_text("派蒙正在搬运每日素材的图标，以后再来探索吧~")
            return

        loading_prompt = await message.reply_text("派蒙可能需要找找图标素材，还请耐心等待哦~")
        await message.reply_chat_action(ChatAction.TYPING)

        # 获取已经缓存的秘境素材信息
        if self.everyday_materials.is_empty():  # 若没有缓存每日素材表的数据
            logger.info("正在获取每日素材缓存")
            await self._refresh_everyday_materials()

        # 尝试获取用户已绑定的原神账号信息
        client, user_owned = await self._get_items_from_user(user_id)
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
                {"width": 1338, "height": 500},
                file_type=file_type,
                ttl=30 * 24 * 60 * 60,
            ),
            self.template_service.render(  # 渲染武器素材页
                "genshin/daily_material/weapon.jinja2",
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

    @handler.command("refresh_daily_material", admin=True, block=False)
    async def refresh(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        message = update.effective_message

        logger.info("用户 {%s}[%s] 刷新[bold]每日素材[/]缓存命令", user.full_name, user.id, extra={"markup": True})
        if self.locks[0].locked():
            notice = await message.reply_text("派蒙还在抄每日素材表呢，我有在好好工作哦~")
            self.add_delete_message_job(notice, delay=10)
            return
        if self.locks[1].locked():
            notice = await message.reply_text("派蒙正在搬运每日素材图标，在努力工作呢！")
            self.add_delete_message_job(notice, delay=10)
            return
        async with self.locks[1]:  # 锁住第二把锁
            notice = await message.reply_text("派蒙正在重新摘抄每日素材表，请稍等~", parse_mode=ParseMode.HTML)
            async with self.locks[0]:  # 锁住第一把锁
                await self._refresh_everyday_materials()
            notice = await notice.edit_text(
                "每日素材表" + ("摘抄<b>完成！</b>" if self.everyday_materials else "坏掉了！等会它再长好了之后我再抄。。。") + "\n正搬运每日素材的图标中。。。",
                parse_mode=ParseMode.HTML,
            )
        time = await self._download_icon(notice)

        async def job(_, n):
            await n.edit_text(n.text_html.split("\n")[0] + "\n每日素材图标搬运<b>完成！</b>", parse_mode=ParseMode.HTML)
            await asyncio.sleep(INTERVAL)
            await notice.delete()

        context.application.job_queue.run_once(
            partial(job, n=notice), when=time + INTERVAL, name="notice_msg_final_job"
        )

    async def _refresh_everyday_materials(self, retry: int = 5):
        """刷新来自 honey impact 的每日素材表"""
        for attempts in range(1, retry + 1):
            try:
                response = await self.client.get("https://genshin.honeyhunterworld.com/?lang=CHS")
            except (HTTPError, SSLZeroReturnError):
                await asyncio.sleep(1)
                if attempts == retry:
                    logger.error("每日素材刷新失败, 请稍后重试")
                else:
                    logger.warning("每日素材刷新失败, 正在重试第 %d 次", attempts)
                continue
            self.everyday_materials = _parse_honey_impact_source(response.content)
            # 当场缓存到文件
            content = self.everyday_materials.json(ensure_ascii=False, separators=(",", ":"))
            async with aiofiles.open(DATA_FILE_PATH, "w", encoding="utf-8") as file:
                await file.write(content)
            return

    async def _assemble_item_from_honey_data(self, item_type: str, item_id: str) -> Optional["ItemData"]:
        """用户拥有的角色和武器中找不到数据时，使用 HoneyImpact 的数据组装出基本信息置灰展示"""
        honey_item = HONEY_DATA[item_type].get(item_id)
        if honey_item is None:
            return None
        try:
            icon = await getattr(self.assets_service, item_type)(item_id).icon()
        except KeyError:
            return None
        return ItemData(
            id=item_id,
            name=typing.cast(str, honey_item[1]),
            rarity=typing.cast(int, honey_item[2]),
            icon=icon.as_uri(),
        )

    async def _download_icon(self, message: "Message") -> float:
        """下载素材图标"""
        asset_list = []
        lock = asyncio.Lock()
        the_time = Value(c_double, time_() - INTERVAL)

        async def edit_message(text):
            """修改提示消息"""
            async with lock:
                if message is not None and time_() >= (the_time.value + INTERVAL):
                    try:
                        await message.edit_text(
                            "\n".join(message.text_html.split("\n")[:2] + [text]), parse_mode=ParseMode.HTML
                        )
                        the_time.value = time_()
                    except (TimedOut, RetryAfter):
                        pass

        async def task(item_id, name, item_type):
            try:
                logger.debug("正在开始下载 %s 的图标素材", name)
                await edit_message(f"正在搬运 <b>{name}</b> 的图标素材。。。")
                asset: AssetsServiceType = getattr(self.assets_service, item_type)(item_id)
                asset_list.append(asset.honey_id)
                # 找到该素材对象的所有图标类型
                # 并根据图标类型找到下载对应图标的函数
                for icon_type in asset.icon_types:
                    await getattr(asset, icon_type)(True)  # 执行下载函数
                logger.debug("%s 的图标素材下载成功", name)
                await edit_message(f"正在搬运 <b>{name}</b> 的图标素材。。。<b>成功！</b>")
            except TimeoutException as exc:
                logger.warning("Httpx [%s]\n%s[%s]", exc.__class__.__name__, exc.request.method, exc.request.url)
                return exc
            except Exception as exc:
                logger.error("图标素材下载出现异常！", exc_info=exc)
                return exc

        notice_text = "图标素材下载完成"
        for TYPE, ITEMS in HONEY_DATA.items():  # 遍历每个对象
            task_list = []
            new_items = []
            for ID, DATA in ITEMS.items():
                if (ITEM := [ID, DATA[1], TYPE]) not in new_items:
                    new_items.append(ITEM)
                    task_list.append(task(*ITEM))
            results = await asyncio.gather(*task_list, return_exceptions=True)  # 等待所有任务执行完成
            for result in results:
                if isinstance(result, TimeoutException):
                    notice_text = "图标素材下载过程中请求超时\n有关详细信息，请查看日志"
                elif isinstance(result, Exception):
                    notice_text = "图标素材下载过程中发生异常\n有关详细信息，请查看日志"
                    break
        try:
            await message.edit_text(notice_text)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.1)
            await message.edit_text(notice_text)
        except Exception as e:
            logger.debug(e)

        logger.info("图标素材下载完成")
        return the_time.value


def _parse_honey_impact_source(source: bytes) -> MaterialsData:
    """
    ## honeyimpact 的源码格式:
    ```html
    <div class="calendar_day_wrap">
      <!-- span 里记录秘境和对应突破素材 -->
      <span class="item_secondary_title">
        <a href="">秘境名<img src="" /></a>
        <div data-days="0"> <!-- data-days 记录星期几 -->
          <a href=""><img src="" /></a> <!-- 「某某」的教导，ID 在 href 中 -->
          <a href=""><img src="" /></a> <!-- 「某某」的指引，ID 在 href 中 -->
          <a href=""><img src="" /></a> <!-- 「某某」的哲学，ID 在 href 中 -->
        </div>
        <div data-days="1"><!-- 同上，但是星期二 --></div>
        <div data-days="2"><!-- 同上，但是星期三 --></div>
        <div data-days="3"><!-- 同上，但是星期四 --></div>
        <div data-days="4"><!-- 同上，但是星期五 --></div>
        <div data-days="5"><!-- 同上，但是星期六 --></div>
        <div data-days="6"><!-- 同上，但是星期日 --></div>
      <span>
      <!-- 这里开始是该秘境下所有可以刷的角色或武器的详细信息 -->
      <!-- 注意这个 a 和上面的 span 在 DOM 中是同级的 -->
      <a href="">
        <!-- data-days 储存可以刷素材的星期几，如 146 指的是 周二/周五/周日 -->
        <div data-assign="char_编号" data-days="146" class="calendar_pic_wrap">
          <img src="" /> <!-- Item ID 在此 -->
          <span> 角色名 </span> <!-- 角色名周围的空格是切实存在的 -->
        </div>
        <!-- 以此类推，该国家所有角色都会被列出 -->
      </a>
      <!-- 炼武秘境格式和精通秘境一样，也是先 span 后 a，会把所有素材都列出来 -->
    </div>
    ```
    """
    honey_item_url_map: Dict[str, str] = {  # 这个变量可以静态化，不过考虑到这个函数三天调用一次，懒得改了
        typing.cast(str, honey_url): typing.cast(str, honey_id)
        for honey_id, [honey_url, _, _] in HONEY_DATA["material"].items()
    }
    calendar = bs4.BeautifulSoup(source, "lxml").select_one(".calendar_day_wrap")
    if calendar is None:
        return MaterialsData()  # 多半是格式错误或者网页数据有误
    everyday_materials: List[Dict[str, "AreaDailyMaterialsData"]] = [{} for _ in range(7)]
    current_country: str = ""
    for element in calendar.find_all(recursive=False):
        element: bs4.Tag
        if element.name == "span":  # 找到代表秘境的 span
            domain_name = next(iter(element)).text  # 第一个孩子节点的 text
            current_country = DOMAIN_AREA_MAP[domain_name]  # 后续处理 a 列表也会用到这个 current_country
            materials_type = f"{DOMAIN_TYPE_MAP[domain_name]}_materials"
            for div in element.find_all("div", recursive=False):  # 7 个 div 对应的是一周中的每一天
                div: bs4.Tag
                weekday = int(div.attrs["data-days"])  # data-days 是一周中的第几天（周一 0，周日 6）
                if current_country not in everyday_materials[weekday]:
                    everyday_materials[weekday][current_country] = AreaDailyMaterialsData()
                materials: List[str] = getattr(everyday_materials[weekday][current_country], materials_type)
                for a in div.find_all("a", recursive=False):  # 当天能刷的所有素材在 a 列表中
                    a: bs4.Tag
                    href = a.attrs["href"]  # 素材 ID 在 href 中
                    honey_url = path.dirname(href).removeprefix("/")
                    materials.append(honey_item_url_map[honey_url])
        if element.name == "a":
            # country_name 是从上面的 span 继承下来的，下面的 item 对应的是角色或者武器
            # element 的第一个 child，也就是 div.calendar_pic_wrap
            calendar_pic_wrap = typing.cast(bs4.Tag, next(iter(element)))  # element 的第一个孩子
            item_name_span = calendar_pic_wrap.select_one("span")
            if item_name_span is None or item_name_span.text.strip() == "旅行者":
                continue  # 因为旅行者的天赋计算比较复杂，不做旅行者的天赋计算
            href = element.attrs["href"]  # Item ID 在 href 中
            item_is_weapon = href.startswith("/i_n")
            # 角色 ID 前缀固定 10000，但是 honey impact 替换成了角色名，剩余部分的数字是真正的 Item ID 组成部分
            item_id = f"{'' if item_is_weapon else '10000'}{''.join(filter(str.isdigit, href))}"
            for weekday in map(int, calendar_pic_wrap.attrs["data-days"]):  # data-days 中存的是星期几可以刷素材
                ascendable_items = everyday_materials[weekday][current_country]
                ascendable_items = ascendable_items.weapon if item_is_weapon else ascendable_items.avatar
                ascendable_items.append(item_id)
    return MaterialsData(__root__=everyday_materials)


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
    items: Iterable[ItemData] = []  # 可培养的角色或武器


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


class AreaDailyMaterialsData(BaseModel):
    """
    AreaDailyMaterialsData 储存某一天某个国家所有可以刷的突破素材以及可以突破的角色和武器
    对应 /daily_material 命令返回的图中一个国家横向这一整条的信息
    """

    avatar_materials: List[str] = []
    """
    avatar_materials 是当日该国所有可以刷的精通和炼武素材的 ID 列表
    举个例子：稻妻周三可以刷「天光」系列材料
    （不用蒙德璃月举例是因为它们每天的角色武器太多了，等稻妻多了再换）
    那么 avatar_materials 将会包括
    - 104326 「天光」的教导
    - 104327 「天光」的指引
    - 104328 「天光」的哲学
    """
    avatar: List[str] = []
    """
    avatar 是排除旅行者后该国当日可以突破天赋的角色 ID 列表
    举个例子：稻妻周三可以刷「天光」系列精通素材
    需要用到「天光」系列的角色有
    - 10000052 雷电将军
    - 10000053 早柚
    - 10000055 五郎
    - 10000058 八重神子
    """
    weapon_materials: List[str] = []
    """
    weapon_materials 是当日该国所有可以刷的炼武素材的 ID 列表
    举个例子：稻妻周三可以刷今昔剧画系列材料
    那么 weapon_materials 将会包括
    - 114033 今昔剧画之恶尉
    - 114034 今昔剧画之虎啮
    - 114035 今昔剧画之一角
    - 114036 今昔剧画之鬼人
    """
    weapon: List[str] = []
    """
    weapon 是该国当日可以突破天赋的武器 ID 列表
    举个例子：稻妻周三可以刷今昔剧画系列炼武素材
    需要用到今昔剧画系列的武器有
    - 11416 笼钓瓶一心
    - 13414 喜多院十文字
    - 13415 「渔获」
    - 13416 断浪长鳍
    - 13509 薙草之稻光
    - 14509 神乐之真意
    """


MaterialsData.update_forward_refs()
