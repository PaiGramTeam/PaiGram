from typing import Any, List, Tuple, Union

from enkanetwork import (
    CharacterInfo,
    DigitType,
    EnkaNetworkAPI,
    EnkaNetworkResponse,
    EnkaServerError,
    Equipments,
    EquipmentsStats,
    EquipmentsType,
    Forbidden,
    HTTPException,
    Stats,
    StatsPercentage,
    UIDNotFounded,
    VaildateUIDError,
)
from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from core.base.assets import DEFAULT_EnkaAssets
from core.baseplugin import BasePlugin
from core.config import config
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user import UserService
from core.user.error import UserNotFoundError
from metadata.shortname import roleToName
from modules.playercards.helpers import ArtifactStatsTheory, fix_skills_level_data
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.log import logger
from utils.models.base import RegionEnum
from utils.patch.aiohttp import AioHttpTimeoutException


class PlayerCards(Plugin, BasePlugin):
    def __init__(self, user_service: UserService = None, template_service: TemplateService = None):
        self.user_service = user_service
        self.client = EnkaNetworkAPI(lang="chs", agent=config.enka_network_api_agent)
        self.template_service = template_service
        self.temp_photo = open("resources/img/kitsune.png", "rb")

    async def _fetch_user(self, uid) -> Union[EnkaNetworkResponse, str]:
        try:
            return await self.client.fetch_user(uid)
        except EnkaServerError:
            return "Enka.Network 服务请求错误，请稍后重试"
        except Forbidden:
            return "Enka.Network 服务请求被拒绝，请稍后重试"
        except AioHttpTimeoutException:
            return "Enka.Network 服务请求超时，请稍后重试"
        except HTTPException:
            return "Enka.Network HTTP 服务请求错误，请稍后重试"
        except UIDNotFounded:
            return "UID 未找到"
        except VaildateUIDError:
            return "UID 未找到"

    @handler(CommandHandler, command="player_card", block=False)
    @handler(MessageHandler, filters=filters.Regex("^角色卡片查询(.*)"), block=False)
    @restricts(restricts_time_of_groups=20, without_overlapping=True)
    @error_callable
    async def player_cards(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = get_all_args(context)
        await message.reply_chat_action(ChatAction.TYPING)
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
            if user_info.region == RegionEnum.HYPERION:
                uid = user_info.yuanshen_uid
            else:
                uid = user_info.genshin_uid
        except UserNotFoundError:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        data = await self._fetch_user(uid)
        if isinstance(data, str):
            await message.reply_text(data)
            return
        if data.characters is None:
            await message.reply_text("请先将角色加入到角色展柜并允许查看角色详情")
            return
        if len(args) == 1:
            character_name = roleToName(args[0])
            logger.info(f"用户 {user.full_name}[{user.id}] 角色卡片查询命令请求 || character_name[{character_name}] uid[{uid}]")
        else:
            logger.info(f"用户 {user.full_name}[{user.id}] 角色卡片查询命令请求")
            buttons = []
            temp = []
            for index, value in enumerate(data.characters):
                temp.append(
                    InlineKeyboardButton(
                        value.name,
                        callback_data=f"get_player_card|{user.id}|{uid}|{value.name}",
                    )
                )
                if index == 3:
                    buttons.append(temp)
                    temp = []
            if len(temp) > 0:
                buttons.append(temp)
            reply_message = await message.reply_photo(
                photo=self.temp_photo, caption="请选择你要查询的角色", reply_markup=InlineKeyboardMarkup(buttons)
            )
            if reply_message.photo:
                self.temp_photo = reply_message.photo[-1].file_id
            return
        for characters in data.characters:
            if characters.name == character_name:
                break
        else:
            await message.reply_text(f"角色展柜中未找到 {character_name}")
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        pnd_data = await RenderTemplate(uid, characters, self.template_service).render()
        await message.reply_photo(pnd_data, filename=f"player_card_{uid}_{character_name}.png")

    @handler(CallbackQueryHandler, pattern=r"^get_player_card\|", block=False)
    @restricts(restricts_time_of_groups=20, without_overlapping=True)
    @error_callable
    async def get_player_cards(self, update: Update, _: CallbackContext) -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_player_card_callback(callback_query_data: str) -> Tuple[str, int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            _result = _data[3]
            logger.debug(f"callback_query_data函数返回 result[{_result}] user_id[{_user_id}] uid[{_uid}]")
            return _result, _user_id, _uid

        result, user_id, uid = await get_player_card_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" "再乱点再按我叫西风骑士团、千岩军、天领奉和教令院了！", show_alert=True)
            return
        logger.info(f"用户 {user.full_name}[{user.id}] 角色卡片查询命令请求 || character_name[{result}] uid[{uid}]")
        data = await self._fetch_user(uid)
        if isinstance(data, str):
            await message.reply_text(data)
            return
        if data.characters is None:
            await message.edit_text("请先将角色加入到角色展柜并允许查看角色详情")
            return
        for characters in data.characters:
            if characters.name == result:
                break
        else:
            await message.edit_text(f"角色展柜中未找到 {result}")
            return
        await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        pnd_data = await RenderTemplate(uid, characters, self.template_service).render()
        await message.edit_media(InputMediaPhoto(pnd_data, filename=f"player_card_{uid}_{result}.png"))


class Artifact(BaseModel):
    """在 enka Equipments model 基础上扩展了圣遗物评分数据"""

    equipment: Equipments
    # 圣遗物评分
    score: float = 0
    # 圣遗物评级
    score_label: str = "E"
    # 圣遗物评级颜色
    score_class: str = ""
    # 圣遗物单行属性评分
    substat_scores: List[float]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for substat_scores in self.substat_scores:
            self.score += substat_scores
        self.score = round(self.score, 1)

        for r in (
            ("D", 10),
            ("C", 16.5),
            ("B", 23.1),
            ("A", 29.7),
            ("S", 36.3),
            ("SS", 42.9),
            ("SSS", 49.5),
            ("ACE", 56.1),
            ("ACE²", 66),
        ):
            if self.score >= r[1]:
                self.score_label = r[0]
                self.score_class = self.get_score_class(r[0])

    @staticmethod
    def get_score_class(label: str) -> str:
        mapping = {
            "D": "text-neutral-400",
            "C": "text-neutral-200",
            "B": "text-violet-400",
            "A": "text-violet-400",
            "S": "text-yellow-400",
            "SS": "text-yellow-400",
            "SSS": "text-yellow-400",
            "ACE": "text-red-500",
            "ACE²": "text-red-500",
        }
        return mapping.get(label, "text-neutral-400")


class RenderTemplate:
    def __init__(self, uid: Union[int, str], character: CharacterInfo, template_service: TemplateService = None):
        self.uid = uid
        self.template_service = template_service
        # 因为需要替换线上 enka 图片地址为本地地址，先克隆数据，避免修改原数据
        self.character = character.copy(deep=True)

    async def render(self):
        # 缓存所有图片到本地
        await self.cache_images()

        artifacts = self.find_artifacts()
        artifact_total_score: float = sum(artifact.score for artifact in artifacts)

        artifact_total_score = round(artifact_total_score, 1)

        artifact_total_score_label: str = "E"
        for r in (
            ("D", 10),
            ("C", 16.5),
            ("B", 23.1),
            ("A", 29.7),
            ("S", 36.3),
            ("SS", 42.9),
            ("SSS", 49.5),
            ("ACE", 56.1),
            ("ACE²", 66),
        ):
            if artifact_total_score / 5 >= r[1]:
                artifact_total_score_label = r[0]

        self.fix_skills_level()

        data = {
            "uid": self.uid,
            "character": self.character,
            "stats": await self.de_stats(),
            "weapon": self.find_weapon(),
            # 圣遗物评分
            "artifact_total_score": artifact_total_score,
            # 圣遗物评级
            "artifact_total_score_label": artifact_total_score_label,
            # 圣遗物评级颜色
            "artifact_total_score_class": Artifact.get_score_class(artifact_total_score_label),
            "artifacts": artifacts,
            # 需要在模板中使用的 enum 类型
            "DigitType": DigitType,
        }

        # html = await self.template_service.render_async(
        #     "genshin/player_card/player_card.html", data
        # )
        # logger.debug(html)

        return await self.template_service.render(
            "genshin/player_card/player_card.html",
            data,
            {"width": 950, "height": 1080},
            full_page=True,
            query_selector=".text-neutral-200",
        )

    async def de_stats(self) -> List[Tuple[str, Any]]:
        stats = self.character.stats
        items: List[Tuple[str, Any]] = []
        logger.debug(self.character.stats)

        # items.append(("基础生命值", stats.BASE_HP.to_rounded()))
        items.append(("生命值", stats.FIGHT_PROP_MAX_HP.to_rounded()))
        # items.append(("基础攻击力", stats.FIGHT_PROP_BASE_ATTACK.to_rounded()))
        items.append(("攻击力", stats.FIGHT_PROP_CUR_ATTACK.to_rounded()))
        # items.append(("基础防御力", stats.FIGHT_PROP_BASE_DEFENSE.to_rounded()))
        items.append(("防御力", stats.FIGHT_PROP_CUR_DEFENSE.to_rounded()))
        items.append(("暴击率", stats.FIGHT_PROP_CRITICAL.to_percentage_symbol()))
        items.append(
            (
                "暴击伤害",
                stats.FIGHT_PROP_CRITICAL_HURT.to_percentage_symbol(),
            )
        )
        items.append(
            (
                "元素充能效率",
                stats.FIGHT_PROP_CHARGE_EFFICIENCY.to_percentage_symbol(),
            )
        )
        items.append(("元素精通", stats.FIGHT_PROP_ELEMENT_MASTERY.to_rounded()))

        # 查找元素伤害加成和治疗加成
        max_stat = StatsPercentage()  # 用于记录最高元素伤害加成 避免武器特效影响
        for stat in stats:
            if 40 <= stat[1].id <= 46:  # 元素伤害加成
                if max_stat.value <= stat[1].value:
                    max_stat = stat[1]
            elif stat[1].id == 29:  # 物理伤害加成
                pass
            elif stat[1].id != 26:  # 治疗加成
                continue
            value = stat[1].to_rounded() if isinstance(stat[1], Stats) else stat[1].to_percentage_symbol()
            if value in ("0%", 0):
                continue
            name = DEFAULT_EnkaAssets.get_hash_map(stat[0])
            if name is None:
                continue
            items.append((name, value))

        if max_stat.id != 0:
            for item in items:
                if "元素伤害加成" in item[0] and max_stat.to_percentage_symbol() != item[1]:
                    items.remove(item)

        return items

    async def cache_images(self) -> None:
        """缓存所有图片到本地"""
        # TODO: 并发下载所有资源
        c = self.character
        # 角色
        c.image.banner.url = await url_to_file(c.image.banner.url)

        # 技能
        for item in c.skills:
            item.icon.url = await url_to_file(item.icon.url)

        # 命座
        for item in c.constellations:
            item.icon.url = await url_to_file(item.icon.url)

        # 装备，包括圣遗物和武器
        for item in c.equipments:
            item.detail.icon.url = await url_to_file(item.detail.icon.url)

    def find_weapon(self) -> Union[Equipments, None]:
        """在 equipments 数组中找到武器，equipments 数组包含圣遗物和武器"""
        for item in self.character.equipments:
            if item.type == EquipmentsType.WEAPON:
                return item

    def find_artifacts(self) -> List[Artifact]:
        """在 equipments 数组中找到圣遗物，并转换成带有分数的 model。equipments 数组包含圣遗物和武器"""

        stats = ArtifactStatsTheory(self.character.name)

        def substat_score(s: EquipmentsStats) -> float:
            return stats.theory(s)

        return [
            Artifact(
                equipment=e,
                # 圣遗物单行属性评分
                substat_scores=[substat_score(s) for s in e.detail.substats],
            )
            for e in self.character.equipments
            if e.type == EquipmentsType.ARTIFACT
        ]

    def fix_skills_level(self) -> None:
        """修复因命座加成导致的技能等级错误"""
        data = fix_skills_level_data.get(self.character.name)
        if not data:
            return
        unlocked_constellations = len([i for i in self.character.constellations if i.unlocked])
        for i in range(2):
            if unlocked_constellations >= 3 + i * 2:
                if data[i] == "E" and len(self.character.skills) >= 2:
                    self.character.skills[1].level += 3
                elif data[i] == "Q" and len(self.character.skills) >= 3:
                    self.character.skills[2].level += 3
