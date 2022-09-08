import asyncio
import json
from typing import Union, Optional, List, Any, Tuple

from enkanetwork import (
    EnkaNetworkAPI,
    Equipments,
    EquipmentsType,
    EquipmentsStats,
    Stats,
    CharacterInfo,
    Assets,
)
from telegram import Update, InputMediaPhoto
from telegram.ext import CommandHandler, filters, CallbackContext, MessageHandler

from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user import UserService
from core.user.error import UserNotFoundError
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file
from utils.log import logger
from utils.models.base import RegionEnum

assets = Assets(lang="chs")


class PlayerCardsCache:
    def __init__(self, redis: RedisDB):
        self.question_qname = "player_cards"
        self.client = redis.client

    async def get_data(self, uid: Union[str, int]) -> Optional[dict]:
        data = await self.client.get(f"{self.question_qname}:{uid}")
        if data is None:
            return None
        json_data = str(data, encoding="utf-8")
        return json.loads(json_data)

    async def set_data(self, uid: Union[str, int], data: dict):
        await self.client.set(f"{self.question_qname}:{uid}", json.dumps(data))


class PlayerCards(Plugin, BasePlugin):
    def __init__(
            self,
            user_service: UserService = None,
            template_service: TemplateService = None,
            redis: RedisDB = None,
    ):
        self.user_service = user_service
        self.client = EnkaNetworkAPI(lang="chs")
        self.template_service = template_service
        self.redis = redis
        self.cache = PlayerCardsCache(redis)

    @handler(CommandHandler, command="player_cards", block=False)
    @handler(MessageHandler, filters=filters.Regex("^刷新(.*)"), block=False)
    @restricts()
    @error_callable
    async def player_cards(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        try:
            user_info = await self.user_service.get_user_by_id(user.id)
            if user_info.region == RegionEnum.HYPERION:
                uid = user_info.yuanshen_uid
            else:
                uid = user_info.genshin_uid
        except UserNotFoundError:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(
                    context, reply_message.chat_id, reply_message.message_id, 30
                )
                self._add_delete_message_job(
                    context, message.chat_id, message.message_id, 30
                )
            return

        data = await self.client.fetch_user(uid)
        pngs = await asyncio.gather(
            *[
                RenderTemplate(uid, c, self.template_service).render()
                for c in data.characters
            ]
        )
        media = [InputMediaPhoto(png) for png in pngs]
        await message.reply_media_group(media)


class Artifact(Equipments):
    score: float
    score_label: str
    substat_scores: List[float]

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        # 圣遗物评分
        self.score = 99
        # 圣遗物评级
        self.score_label = "SSS"

        # 圣遗物单行属性评分
        self.substat_scores = [self.substat_score(s) for s in self.detail.substats]

        # 总分对齐系数
        self.score_k = "100%"

    def substat_score(stat: EquipmentsStats) -> float:
        return 99


class RenderTemplate:
    def __init__(
            self,
            uid: Union[int, str],
            character: CharacterInfo,
            template_service: TemplateService = None,
    ):
        self.uid = uid
        self.template_service = template_service
        # 因为需要替换线上 enka 图片地址为本地地址，先克隆数据，避免修改原数据
        self.character = character.copy()

    async def render(self):
        # 缓存所有图片到本地
        await self.cache_images()

        data = {
            "uid": self.uid,
            "character": self.character,
            "stats": await self.de_stats(),
            "weapon": self.find_weapon(),
            # 圣遗物评分
            "artifact_total_score": 180.5,
            # 圣遗物评级
            "artifact_total_score_label": "S",
            "artifacts": self.find_artifacts(),
        }

        # html = await self.template_service.render_async(
        #     "genshin/player_card", "player_card.html", data
        # )
        # logger.debug(html)

        return await self.template_service.render(
            "genshin/player_card",
            "player_card.html",
            data,
            {"width": 845, "height": 1080},
            full_page=True,
        )

    async def de_stats(self) -> List[Tuple[str, Any]]:
        stats = self.character.stats
        items: List[Tuple[str, Any]] = []
        logger.debug(self.character.stats)

        items.append(("基础生命值", stats.BASE_HP.to_rounded()))
        items.append(("生命值", stats.FIGHT_PROP_MAX_HP.to_rounded()))
        items.append(("基础攻击力", stats.FIGHT_PROP_BASE_ATTACK.to_rounded()))
        items.append(("攻击力", stats.FIGHT_PROP_CUR_ATTACK.to_rounded()))
        items.append(("基础防御力", stats.FIGHT_PROP_BASE_DEFENSE.to_rounded()))
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
        for stat in stats:
            if 40 <= stat[1].id <= 46:  # 元素伤害加成
                pass
            elif stat[1].id == 29:  # 物理伤害加成
                pass
            elif stat[1].id == 26:  # 治疗加成
                pass
            else:
                continue
            value = (
                stat[1].to_rounded()
                if isinstance(stat[1], Stats)
                else stat[1].to_percentage_symbol()
            )
            if value in ("0%", 0):
                continue
            name = assets.get_hash_map(stat[0])
            if name is None:
                continue
            logger.info(f"{name} -> {value}")
            items.append((name, value))

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
        return [
            Artifact(e)
            for e in self.character.equipments
            if e.type == EquipmentsType.ARTIFACT
        ]
