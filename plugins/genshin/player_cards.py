import copy
import math
from typing import Any, List, Tuple, Union, Optional, TYPE_CHECKING, Dict

from enkanetwork import (
    DigitType,
    EnkaNetworkResponse,
    EnkaServerError,
    Equipments,
    EquipmentsType,
    HTTPException,
    Stats,
    StatsPercentage,
    VaildateUIDError,
    EnkaServerMaintanance,
    EnkaServerUnknown,
    EnkaServerRateLimit,
    EnkaPlayerNotFound,
    TimedOut,
)
from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.config import config
from core.dependence.assets import DEFAULT_EnkaAssets, AssetsService
from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.players import PlayersService
from core.services.template.services import TemplateService
from metadata.shortname import roleToName
from modules.apihelper.client.components.remote import Remote
from modules.playercards.file import PlayerCardsFile
from modules.playercards.helpers import ArtifactStatsTheory
from utils.enkanetwork import RedisCache, EnkaNetworkAPI
from utils.helpers import download_resource
from utils.log import logger
from utils.uid import mask_number

try:
    from python_genshin_artifact.calculator import get_damage_analysis
    from python_genshin_artifact.enka.characters import characters_map
    from python_genshin_artifact.enka.enka_parser import enka_parser
    from python_genshin_artifact.models.calculator import CalculatorConfig
    from python_genshin_artifact.models.skill import SkillInfo

    GENSHIN_ARTIFACT_FUNCTION_AVAILABLE = True
except ImportError as exc:
    get_damage_analysis = None
    characters_map = {}
    enka_parser = None
    CalculatorConfig = None
    SkillInfo = None
    Assets = None

    GENSHIN_ARTIFACT_FUNCTION_AVAILABLE = False

if TYPE_CHECKING:
    from enkanetwork import CharacterInfo, EquipmentsStats
    from telegram.ext import ContextTypes
    from telegram import Update, Message

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


class PlayerCards(Plugin):
    def __init__(
        self,
        player_service: PlayersService,
        template_service: TemplateService,
        assets_service: AssetsService,
        redis: RedisDB,
    ):
        self.player_service = player_service
        self.client = EnkaNetworkAPI(lang="chs", user_agent=config.enka_network_api_agent, cache=False)
        self.cache = RedisCache(redis.client, key="plugin:player_cards:enka_network", ex=60)
        self.player_cards_file = PlayerCardsFile()
        self.assets_service = assets_service
        self.template_service = template_service
        self.kitsune: Optional[str] = None
        self.fight_prop_rule: Dict[str, Dict[str, float]] = {}
        self.damage_config: Dict = {}

    async def initialize(self):
        await self._refresh()

    async def _refresh(self):
        self.fight_prop_rule = await Remote.get_fight_prop_rule_data()
        self.damage_config = await Remote.get_damage_data()

    async def _update_enka_data(self, uid) -> Union[EnkaNetworkResponse, str]:
        try:
            data = await self.cache.get(uid)
            if data is not None:
                return EnkaNetworkResponse.parse_obj(data)
            user = await self.client.http.fetch_user_by_uid(uid)
            data = user["content"].decode("utf-8", "surrogatepass")  # type: ignore
            data = jsonlib.loads(data)
            data = await self.player_cards_file.merge_info(uid, data)
            await self.cache.set(uid, data)
            return EnkaNetworkResponse.parse_obj(data)
        except TimedOut:
            error = "Enka.Network 服务请求超时，请稍后重试"
        except EnkaServerRateLimit:
            error = "Enka.Network 已对此API进行速率限制，请稍后重试"
        except EnkaServerMaintanance:
            error = "Enka.Network 正在维护，请等待5-8小时或1天"
        except EnkaServerError:
            error = "Enka.Network 服务请求错误，请稍后重试"
        except EnkaServerUnknown:
            error = "Enka.Network 服务瞬间爆炸，请稍后重试"
        except EnkaPlayerNotFound:
            error = "UID 未找到，可能为服务器抽风，请稍后重试"
        except VaildateUIDError:
            error = "未找到玩家，请检查您的UID/用户名"
        except HTTPException:
            error = "Enka.Network HTTP 服务请求错误，请稍后重试"
        return error

    async def _load_data_as_enka_response(self, uid) -> Optional[EnkaNetworkResponse]:
        data = await self.player_cards_file.load_history_info(uid)
        if data is None:
            return None
        return EnkaNetworkResponse.parse_obj(data)

    async def _load_history(self, uid) -> Optional[Dict]:
        return await self.player_cards_file.load_history_info(uid)

    async def get_uid_and_ch(
        self, user_id: int, args: List[str], reply: Optional["Message"]
    ) -> Tuple[Optional[int], Optional[str]]:
        """通过消息获取 uid，优先级：args > reply > self"""
        uid, ch_name, user_id_ = None, None, user_id
        if args:
            for i in args:
                if i is not None:
                    if i.isdigit() and len(i) == 9:
                        uid = int(i)
                    else:
                        ch_name = roleToName(i)
        if reply:
            try:
                user_id_ = reply.from_user.id
            except AttributeError:
                pass
        if not uid:
            player_info = await self.player_service.get_player(user_id_)
            if player_info is not None:
                uid = player_info.player_id
            if (not uid) and (user_id_ != user_id):
                player_info = await self.player_service.get_player(user_id)
                if player_info is not None:
                    uid = player_info.player_id
        return uid, ch_name

    @handler.command(command="player_card", block=False)
    @handler.message(filters=filters.Regex("^角色卡片查询(.*)"), block=False)
    async def player_cards(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        message = update.effective_message
        args = self.get_args(context)
        await message.reply_chat_action(ChatAction.TYPING)
        uid, character_name = await self.get_uid_and_ch(user.id, args, message.reply_to_message)
        if uid is None:
            buttons = [
                [
                    InlineKeyboardButton(
                        "点我绑定账号",
                        url=create_deep_linked_url(context.bot.username, "set_uid"),
                    )
                ]
            ]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                self.add_delete_message_job(reply_message, delay=30)

                self.add_delete_message_job(message, delay=30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
            return
        original_data = await self._load_history(uid)
        if original_data is None or len(original_data.get("avatarInfoList", [])) == 0:
            if isinstance(self.kitsune, str):
                photo = self.kitsune
            else:
                photo = open("resources/img/kitsune.png", "rb")
            buttons = [
                [
                    InlineKeyboardButton(
                        "更新面板",
                        callback_data=f"update_player_card|{user.id}|{uid}",
                    )
                ]
            ]
            reply_message = await message.reply_photo(
                photo=photo,
                caption="角色列表未找到，请尝试点击下方按钮从 EnkaNetwork 更新角色列表",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            if reply_message.photo:
                self.kitsune = reply_message.photo[-1].file_id
            return
        enka_response = EnkaNetworkResponse.parse_obj(copy.deepcopy(original_data))
        if character_name is not None:
            logger.info(
                "用户 %s[%s] 角色卡片查询命令请求 || character_name[%s] uid[%s]",
                user.full_name,
                user.id,
                character_name,
                uid,
            )
        else:
            logger.info("用户 %s[%s] 角色卡片查询命令请求", user.full_name, user.id)
            ttl = await self.cache.ttl(uid)
            if enka_response.characters is None or len(enka_response.characters) == 0:
                buttons = [
                    [
                        InlineKeyboardButton(
                            "更新面板",
                            callback_data=f"update_player_card|{user.id}|{uid}",
                        )
                    ]
                ]
            else:
                buttons = self.gen_button(enka_response, user.id, uid, update_button=ttl < 0)
            if isinstance(self.kitsune, str):
                photo = self.kitsune
            else:
                photo = open("resources/img/kitsune.png", "rb")
            reply_message = await message.reply_photo(
                photo=photo,
                caption="请选择你要查询的角色",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            if reply_message.photo:
                self.kitsune = reply_message.photo[-1].file_id
            return
        for characters in enka_response.characters:
            if characters.name == character_name:
                break
        else:
            await message.reply_text(f"角色展柜中未找到 {character_name} ，请检查角色是否存在于角色展柜中，或者等待角色数据更新后重试")
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        original_data: Optional[Dict] = None
        if GENSHIN_ARTIFACT_FUNCTION_AVAILABLE:
            original_data = await self._load_history(uid)
        render_result = await RenderTemplate(
            uid,
            characters,
            self.fight_prop_rule,
            self.damage_config,
            self.template_service,
            original_data,
        ).render()  # pylint: disable=W0631
        await render_result.reply_photo(
            message,
            filename=f"player_card_{uid}_{character_name}.png",
        )

    @handler.callback_query(pattern=r"^update_player_card\|", block=False)
    async def update_player_card(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        message = update.effective_message
        callback_query = update.callback_query

        async def get_player_card_callback(callback_query_data: str) -> Tuple[int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            logger.debug("callback_query_data函数返回 user_id[%s] uid[%s]", _user_id, _uid)
            return _user_id, _uid

        user_id, uid = await get_player_card_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return

        ttl = await self.cache.ttl(uid)

        if ttl > 0:
            await callback_query.answer(text=f"请等待 {ttl} 秒后再更新", show_alert=True)
            return

        await message.reply_chat_action(ChatAction.TYPING)
        await callback_query.answer(text="正在从 EnkaNetwork 获取角色列表 请不要重复点击按钮")
        data = await self._update_enka_data(uid)
        if isinstance(data, str):
            await callback_query.answer(text=data, show_alert=True)
            return
        if data.characters is None or len(data.characters) == 0:
            await callback_query.answer("请先将角色加入到角色展柜并允许查看角色详情后再使用此功能，如果已经添加了角色，请等待角色数据更新后重试", show_alert=True)
            await message.delete()
            return
        buttons = self.gen_button(data, user.id, uid, update_button=False)
        render_data = await self.parse_holder_data(data)
        holder = await self.template_service.render(
            "genshin/player_card/holder.jinja2",
            render_data,
            viewport={"width": 750, "height": 580},
            ttl=60 * 10,
            caption="更新角色列表成功，请选择你要查询的角色",
        )
        await holder.edit_media(message, reply_markup=InlineKeyboardMarkup(buttons))

    @handler.callback_query(pattern=r"^get_player_card\|", block=False)
    async def get_player_cards(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_player_card_callback(
            callback_query_data: str,
        ) -> Tuple[str, int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            _result = _data[3]
            logger.debug(
                "callback_query_data函数返回 result[%s] user_id[%s] uid[%s]",
                _result,
                _user_id,
                _uid,
            )
            return _result, _user_id, _uid

        result, user_id, uid = await get_player_card_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        if result == "empty_data":
            await callback_query.answer(text="此按钮不可用", show_alert=True)
            return
        page = 0
        if result.isdigit():
            page = int(result)
            logger.info(
                "用户 %s[%s] 角色卡片查询命令请求 || page[%s] uid[%s]",
                user.full_name,
                user.id,
                page,
                uid,
            )
        else:
            logger.info(
                "用户 %s[%s] 角色卡片查询命令请求 || character_name[%s] uid[%s]",
                user.full_name,
                user.id,
                result,
                uid,
            )
        original_data = await self._load_history(uid)
        enka_response = EnkaNetworkResponse.parse_obj(copy.deepcopy(original_data))
        if enka_response.characters is None or len(enka_response.characters) == 0:
            await callback_query.answer("请先将角色加入到角色展柜并允许查看角色详情后再使用此功能，如果已经添加了角色，请等待角色数据更新后重试", show_alert=True)
            await message.delete()
            return
        if page:
            buttons = self.gen_button(enka_response, user.id, uid, page, await self.cache.ttl(uid) <= 0)
            await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            await callback_query.answer(f"已切换到第 {page} 页", show_alert=False)
            return
        for characters in enka_response.characters:
            if characters.name == result:
                break
        else:
            await message.delete()
            await callback_query.answer(f"角色展柜中未找到 {result} ，请检查角色是否存在于角色展柜中，或者等待角色数据更新后重试", show_alert=True)
            return
        await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        render_result = await RenderTemplate(
            uid, characters, self.fight_prop_rule, self.damage_config, self.template_service, original_data
        ).render()  # pylint: disable=W0631
        render_result.filename = f"player_card_{uid}_{result}.png"
        await render_result.edit_media(message)

    @staticmethod
    def gen_button(
        data: EnkaNetworkResponse,
        user_id: Union[str, int],
        uid: int,
        page: int = 1,
        update_button: bool = True,
    ) -> List[List[InlineKeyboardButton]]:
        """生成按钮"""
        buttons = []
        if data.characters:
            buttons = [
                InlineKeyboardButton(
                    value.name,
                    callback_data=f"get_player_card|{user_id}|{uid}|{value.name}",
                )
                for value in data.characters
                if value.name
            ]
        all_buttons = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
        send_buttons = all_buttons[(page - 1) * 3 : page * 3]
        last_page = page - 1 if page > 1 else 0
        all_page = math.ceil(len(all_buttons) / 3)
        next_page = page + 1 if page < all_page and all_page > 1 else 0
        last_button = []
        if last_page:
            last_button.append(
                InlineKeyboardButton(
                    "<< 上一页",
                    callback_data=f"get_player_card|{user_id}|{uid}|{last_page}",
                )
            )
        if last_page or next_page:
            last_button.append(
                InlineKeyboardButton(
                    f"{page}/{all_page}",
                    callback_data=f"get_player_card|{user_id}|{uid}|empty_data",
                )
            )
        if update_button:
            last_button.append(
                InlineKeyboardButton(
                    "更新面板",
                    callback_data=f"update_player_card|{user_id}|{uid}",
                )
            )
        if next_page:
            last_button.append(
                InlineKeyboardButton(
                    "下一页 >>",
                    callback_data=f"get_player_card|{user_id}|{uid}|{next_page}",
                )
            )
        if last_button:
            send_buttons.append(last_button)
        return send_buttons

    async def parse_holder_data(self, data: EnkaNetworkResponse) -> dict:
        """
        生成渲染所需数据
        """
        characters_data = []
        for idx, character in enumerate(data.characters):
            characters_data.append(
                {
                    "level": character.level,
                    "element": character.element.name,
                    "constellation": character.constellations_unlocked,
                    "rarity": character.rarity,
                    "icon": (await self.assets_service.avatar(character.id).icon()).as_uri(),
                }
            )
            if idx > 6:
                break
        return {
            "uid": mask_number(data.uid),
            "level": data.player.level,
            "signature": data.player.signature,
            "characters": characters_data,
        }


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
    def __init__(
        self,
        uid: Union[int, str],
        character: "CharacterInfo",
        fight_prop_rule: Dict[str, Dict[str, float]],
        damage_config: Dict,
        template_service: TemplateService,
        original_data: Optional[Dict] = None,
    ):
        self.uid = uid
        self.template_service = template_service
        # 因为需要替换线上 enka 图片地址为本地地址，先克隆数据，避免修改原数据
        self.character = character.copy(deep=True)
        self.fight_prop_rule = fight_prop_rule
        self.original_data = original_data
        self.damage_config = damage_config

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

        data = {
            "uid": mask_number(self.uid),
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
            "damage_function_available": False,
            "damage_info": [],
        }

        if GENSHIN_ARTIFACT_FUNCTION_AVAILABLE:
            character_name = characters_map.get(self.character.id)
            damage_config = self.damage_config.get(character_name)
            if damage_config is not None:
                data["damage_function_available"] = True
                data["damage_info"] = self.render_damage(damage_config)

        return await self.template_service.render(
            "genshin/player_card/player_card.jinja2",
            data,
            full_page=True,
            query_selector=".text-neutral-200",
            ttl=7 * 24 * 60 * 60,
        )

    def render_damage(self, damage_config: Optional[Dict]) -> List:
        character, weapon, artifacts = enka_parser(self.original_data, self.character.id)
        character_name = character.name
        if damage_config is None:
            damage_config = self.damage_config.get(character_name)
        skills = damage_config.get("skills")
        config_skill = damage_config.get("config_skill")
        if config_skill is not None:
            config_skill = {character_name: config_skill}
        else:
            config_skill = "NoConfig"
        character_config = damage_config.get("config")
        artifact_config = damage_config.get("artifact_config")
        if character_config is not None:
            character.params = {character_name: character_config}
        config_weapon = damage_config.get("config_weapon")
        if config_weapon is not None:
            _weapon_config = config_weapon.get(weapon.name)
            if _weapon_config is not None:
                weapon.params = {weapon.name: _weapon_config}
        damage = []
        for skill in skills:
            index = skill.get("index")
            skill_info = SkillInfo(index=index, config=config_skill)
            calculator_config = CalculatorConfig(
                character=character,
                weapon=weapon,
                artifacts=artifacts,
                skill=skill_info,
                artifact_config=artifact_config,
            )
            damage_analysis = get_damage_analysis(calculator_config)
            damage_key = skill.get("damage_key")
            damage_value = getattr(damage_analysis, damage_key)
            if damage_value is not None:
                damage_info = {"damage": damage_value, "skill_info": skill}
                damage.append(damage_info)

        return damage

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
        c.image.banner.url = await download_resource(c.image.banner.url)

        # 技能
        for item in c.skills:
            item.icon.url = await download_resource(item.icon.url)

        # 命座
        for item in c.constellations:
            item.icon.url = await download_resource(item.icon.url)

        # 装备，包括圣遗物和武器
        for item in c.equipments:
            item.detail.icon.url = await download_resource(item.detail.icon.url)

    def find_weapon(self) -> Optional[Equipments]:
        """在 equipments 数组中找到武器，equipments 数组包含圣遗物和武器"""
        for item in self.character.equipments:
            if item.type == EquipmentsType.WEAPON:
                return item
        return None

    def find_artifacts(self) -> List[Artifact]:
        """在 equipments 数组中找到圣遗物，并转换成带有分数的 model。equipments 数组包含圣遗物和武器"""

        stats = ArtifactStatsTheory(self.character.name, self.fight_prop_rule)

        def substat_score(s: "EquipmentsStats") -> float:
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
