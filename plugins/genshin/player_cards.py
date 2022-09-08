import json
from typing import Union, Optional, List, cast

from enkanetwork import EnkaNetworkAPI, Equipments, EquipmentsType, DigitType, Stats, CharacterInfo, \
    EnkaNetworkResponse, Assets
from telegram import Update
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
    def __init__(self, user_service: UserService = None, template_service: TemplateService = None,
                 redis: RedisDB = None):
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
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        # 注意！！！！！！！！！！！！！！！！！！！！！！！！！！！！
        # 调试使用 非常建议手动缓存到cache 因为enka时不时会奔溃
        # data = await self.client.fetch_user(uid)
        d = await self.cache.get_data(uid)
        data = EnkaNetworkResponse.parse_obj(d)
        character_info = data.characters[0]
        render_template = RenderTemplate(uid, character_info, self.template_service)
        png_data = await render_template.render()
        await message.reply_photo(png_data)


class RenderTemplate:
    def __init__(self, uid: Union[int, str], character: CharacterInfo, template_service: TemplateService = None):
        self.uid = uid
        self.template_service = template_service
        self.character = character

    async def render(self):
        player_card_data = {
            "infos": []
        }
        background = f"img/bg-{self.character.element.name.lower()}.jpg"
        player_card_data["background"] = background
        player_card_data["image_banner"] = await url_to_file(self.character.image.banner.url)
        player_card_data["friendship_level"] = self.character.friendship_level
        player_card_data["level"] = self.character.level
        player_card_data["uid"] = self.uid

        player_card_data["constellations"] = await self.de_constellations()
        player_card_data["skills"] = await self.de_skills()
        player_card_data["stats"] = await self.de_stats()
        artifacts = await self.de_artifacts()
        for artifact in artifacts:
            player_card_data["infos"].append(artifact)
        data = await self.template_service.render_async('genshin/player_card', "player_card.html", player_card_data)
        print(data)
        return await self.template_service.render('genshin/player_card', "player_card.html", player_card_data,
                                                  {"width": 900, "height": 1080}, full_page=True)

    async def de_stats(self) -> str:
        stats_data = {
            "names": [],
            "values": []
        }
        stats_data["names"].append("基础生命值")
        stats_data["values"].append(self.character.stats.BASE_HP.to_rounded())
        stats_data["names"].append("生命值")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_MAX_HP.to_rounded())
        stats_data["names"].append("基础攻击力")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_BASE_ATTACK.to_rounded())
        stats_data["names"].append("攻击力")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_CUR_ATTACK.to_rounded())
        stats_data["names"].append("基础防御力")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_BASE_DEFENSE.to_rounded())
        stats_data["names"].append("防御力")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_CUR_DEFENSE.to_rounded())
        stats_data["names"].append("暴击率")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_CRITICAL.to_percentage_symbol())
        stats_data["names"].append("暴击伤害")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_CRITICAL_HURT.to_percentage_symbol())
        stats_data["names"].append("元素充能效率")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_CHARGE_EFFICIENCY.to_percentage_symbol())
        stats_data["names"].append("元素精通")
        stats_data["values"].append(self.character.stats.FIGHT_PROP_ELEMENT_MASTERY.to_rounded())
        # 查找元素伤害加成和治疗加成
        for stat in self.character.stats:
            if "_ADD_HURT" not in stat[0] or "FIGHT_PROP_HEAL_ADD" != stat[0] or "NONEXTRA" in stat[0] or "HIT" in stat[0]:
                continue
            name = assets.get_hash_map(stat[0])
            if name is None:
                continue
            value = stat[1].to_rounded() if isinstance(stat[1], Stats) else stat[1].to_percentage_symbol()
            if value == 0 or value == "0%":
                continue
            logger.info(f"{name} -> {value}")
            stats_data["names"].append(name)
            stats_data["values"].append(value)
        return await self.template_service.render_async('genshin/player_card', "stats.html", stats_data)

    async def de_skills(self) -> str:
        background = f"img/talent-{self.character.element.name.lower()}.png"
        skills_data = {
            "items": []
        }
        for skill in self.character.skills:
            img = await url_to_file(skill.icon.url)
            skills_data["items"].append({
                "background": background,
                "img": img,
                "level": skill.level
            })
        return await self.template_service.render_async('genshin/player_card', "skills.html", skills_data)

    async def de_constellations(self) -> str:
        background = f"img/talent-{self.character.element.name.lower()}.png"
        artifacts_data = {
            "items": []
        }
        for constellation in self.character.constellations:
            artifacts_data["items"].append({
                "background": background,
                "img": constellation.icon.url
            })
        return await self.template_service.render_async('genshin/player_card', "constellations.html", artifacts_data)

    async def de_artifacts(self) -> List[str]:
        html_list: List[str] = []
        for artifact in filter(lambda x: x.type == EquipmentsType.ARTIFACT, self.character.equipments):
            artifact = cast(Equipments, artifact)
            img = await url_to_file(artifact.detail.icon.url)
            artifacts_data = {
                "img": img,
                "level": artifact.level,
                "name": artifact.detail.name,
                "detail_names": [],
                "detail_values": [],
                "detail_scores": []
            }
            artifacts_data["detail_names"].append(artifact.detail.mainstats.name)
            artifacts_data["detail_values"].append(
                f"{artifact.detail.mainstats.value}{'%' if artifact.detail.mainstats.type == DigitType.PERCENT else ''}")
            artifacts_data["detail_scores"].append("-")
            for substate in artifact.detail.substats:
                artifacts_data["detail_names"].append(substate.name)
                artifacts_data["detail_values"].append(
                    f"{substate.value}{'%' if substate.type == DigitType.PERCENT else ''}")
                artifacts_data["detail_scores"].append(substate)
            html = await self.template_service.render_async('genshin/player_card', "artifacts.html", artifacts_data)
            html_list.append(html)
        return html_list
