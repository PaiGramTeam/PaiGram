import math
from typing import TYPE_CHECKING, Union, List, Optional, Tuple, Dict

import aiofiles
from enkanetwork import (
    EnkaNetworkResponse,
    EnkaServerError,
    HTTPException,
    VaildateUIDError,
    EnkaServerMaintanance,
    EnkaServerUnknown,
    EnkaServerRateLimit,
    EnkaPlayerNotFound,
    TimedOut,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import filters, CallbackQueryHandler
from telegram.helpers import create_deep_linked_url

from core.dependence.assets import AssetsService

from core.plugin import Plugin
from gram_core.config import config
from gram_core.dependence.redisdb import RedisDB
from gram_core.plugin import handler
from gram_core.services.players import PlayersService
from gram_core.services.template.services import TemplateService
from metadata.shortname import roleToName
from modules.playercards.file import PlayerCardsFile
from utils.const import PROJECT_ROOT
from utils.enkanetwork import RedisCache, EnkaNetworkAPI
from utils.log import logger
from utils.uid import mask_number

try:
    from python_genshin_artifact.calculator import get_damage_analysis
    from python_genshin_artifact.enka.enka_parser import enka_parser
    from python_genshin_artifact.models.calculator import CalculatorConfig
    from python_genshin_artifact.models.skill import SkillInfo
    from python_genshin_artifact.assets import Assets

    assets = Assets()

    GENSHIN_ARTIFACT_FUNCTION_AVAILABLE = True
except ImportError as exc:
    get_damage_analysis = None
    enka_parser = None
    CalculatorConfig = None
    SkillInfo = None
    Assets = None

    GENSHIN_ARTIFACT_FUNCTION_AVAILABLE = False
    # logger.debug("python_genshin_artifact 导入失败", exc_info=exc)

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

if TYPE_CHECKING:
    from telegram import Update, InlineKeyboardButton
    from telegram.ext import ContextTypes


DAMAGE_CONFIG_PATH = PROJECT_ROOT.joinpath("metadata", "damage.json")


class Damage(Plugin):
    def __init__(
        self,
        player_service: PlayersService,
        template_service: TemplateService,
        assets_service: AssetsService,
        redis: RedisDB,
    ):
        self.player_service = player_service
        self.client = EnkaNetworkAPI(lang="chs", user_agent=config.enka_network_api_agent, cache=False)
        self.cache = RedisCache(redis.client, key="plugin:damage:enka_network", ex=60)
        self.damages_file = PlayerCardsFile()
        self.assets_service = assets_service
        self.template_service = template_service
        self.kitsune: Optional[str] = None
        self.damage_config: Dict = {}

    async def initialize(self) -> None:
        async with aiofiles.open(DAMAGE_CONFIG_PATH, "r", encoding="utf-8") as f:
            self.damage_config = jsonlib.loads(await f.read())

    @handler.command("damage_config", block=False, admin=True)
    async def damage_config_refuse(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        message = update.effective_message
        async with aiofiles.open(DAMAGE_CONFIG_PATH, "r", encoding="utf-8") as f:
            self.damage_config = jsonlib.loads(await f.read())
        await message.reply_text("刷新成功")

    async def _update_enka_data(self, uid) -> Union[EnkaNetworkResponse, str]:
        try:
            data = await self.cache.get(uid)
            if data is not None:
                return EnkaNetworkResponse.parse_obj(data)
            user = await self.client.http.fetch_user_by_uid(uid)
            data = user["content"].decode("utf-8", "surrogatepass")  # type: ignore
            data = jsonlib.loads(data)
            data = await self.damages_file.merge_info(uid, data)
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

    async def _load_history(self, uid) -> Optional[Dict]:
        return await self.damages_file.load_history_info(uid)

    @handler.command("damage", block=False)
    async def damages(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        message = update.effective_message
        args = self.get_args(context)
        await message.reply_chat_action(ChatAction.TYPING)
        player_info = await self.player_service.get_player(user.id)
        if player_info is None:
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
        data = await self._load_history(player_info.player_id)
        if data is None:
            if isinstance(self.kitsune, str):
                photo = self.kitsune
            else:
                photo = open("resources/img/kitsune.png", "rb")
            buttons = [
                [
                    InlineKeyboardButton(
                        "更新面板",
                        callback_data=f"update_damage|{user.id}|{player_info.player_id}",
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
        enka_network_response = EnkaNetworkResponse.parse_obj(data.copy())
        if len(args) == 1:
            character_name = roleToName(args[0])
            logger.info(
                "用户 %s[%s] 伤害查询命令请求 || character_name[%s] uid[%s]",
                user.full_name,
                user.id,
                character_name,
                player_info.player_id,
            )
        else:
            logger.info("用户 %s[%s] 伤害查询命令请求", user.full_name, user.id)
            ttl = await self.cache.ttl(player_info.player_id)
            if enka_network_response.characters is None or len(enka_network_response.characters) == 0:
                buttons = [
                    [
                        InlineKeyboardButton(
                            "更新面板",
                            callback_data=f"update_damage|{user.id}|{player_info.player_id}",
                        )
                    ]
                ]
            else:
                buttons = self.gen_button(enka_network_response, user.id, player_info.player_id, update_button=ttl < 0)
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
        for characters in enka_network_response.characters:
            if characters.name == character_name:
                avatar_id = characters.id
                break
        else:
            await message.reply_text(f"角色展柜中未找到 {character_name} ，请检查角色是否存在于角色展柜中，或者等待角色数据更新后重试")
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        render_result = await RenderTemplate(
            player_info.player_id, data, avatar_id, self.template_service, self.damage_config
        ).render()  # pylint: disable=W0631
        await render_result.reply_photo(
            message,
            filename=f"damage_{player_info.player_id}_{character_name}.png",
        )

    @handler(CallbackQueryHandler, pattern=r"^update_damage\|", block=False)
    async def update_damage(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        message = update.effective_message
        callback_query = update.callback_query

        async def get_damage_callback(callback_query_data: str) -> Tuple[int, int]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            logger.debug("callback_query_data函数返回 user_id[%s] uid[%s]", _user_id, _uid)
            return _user_id, _uid

        user_id, uid = await get_damage_callback(callback_query.data)
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
            "genshin/damage/holder.jinja2",
            render_data,
            viewport={"width": 750, "height": 580},
            ttl=60 * 10,
            caption="更新角色列表成功，请选择你要查询的角色",
        )
        await holder.edit_media(message, reply_markup=InlineKeyboardMarkup(buttons))

    @handler(CallbackQueryHandler, pattern=r"^get_damage\|", block=False)
    async def get_damages(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_damage_callback(
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

        result, user_id, uid = await get_damage_callback(callback_query.data)
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
                "用户 %s[%s] 伤害查询命令请求 || page[%s] uid[%s]",
                user.full_name,
                user.id,
                page,
                uid,
            )
        else:
            logger.info(
                "用户 %s[%s] 伤害查询命令请求 || character_name[%s] uid[%s]",
                user.full_name,
                user.id,
                result,
                uid,
            )
        data = await self._load_history(uid)
        if isinstance(data, str):
            await message.reply_text(data)
            return
        enka_network_response = EnkaNetworkResponse.parse_obj(data)
        new_data = await self._load_history(uid)
        if enka_network_response.characters is None or len(enka_network_response.characters) == 0:
            await callback_query.answer("请先将角色加入到角色展柜并允许查看角色详情后再使用此功能，如果已经添加了角色，请等待角色数据更新后重试", show_alert=True)
            await message.delete()
            return
        if page:
            buttons = self.gen_button(enka_network_response, user.id, uid, page, not await self.cache.ttl(uid) > 0)
            await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            await callback_query.answer(f"已切换到第 {page} 页", show_alert=False)
            return
        for characters in enka_network_response.characters:
            if characters.name == result:
                avatar_id = characters.id
                break
        else:
            await message.delete()
            await callback_query.answer(f"角色展柜中未找到 {result} ，请检查角色是否存在于角色展柜中，或者等待角色数据更新后重试", show_alert=True)
            return
        await callback_query.answer(text="正在渲染图片中 请稍等 请不要重复点击按钮", show_alert=False)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        render_result = await RenderTemplate(
            uid, new_data, avatar_id, self.template_service, self.damage_config
        ).render()  # pylint: disable=W0631
        render_result.filename = f"damage_{uid}_{result}.png"
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
                    callback_data=f"get_damage|{user_id}|{uid}|{value.name}",
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
                    callback_data=f"get_damage|{user_id}|{uid}|{last_page}",
                )
            )
        if last_page or next_page:
            last_button.append(
                InlineKeyboardButton(
                    f"{page}/{all_page}",
                    callback_data=f"get_damage|{user_id}|{uid}|empty_data",
                )
            )
        if update_button:
            last_button.append(
                InlineKeyboardButton(
                    "更新面板",
                    callback_data=f"update_damage|{user_id}|{uid}",
                )
            )
        if next_page:
            last_button.append(
                InlineKeyboardButton(
                    "下一页 >>",
                    callback_data=f"get_damage|{user_id}|{uid}|{next_page}",
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


class RenderTemplate:
    def __init__(
        self,
        uid: int,
        enka_data: Dict,
        avatar_id: int,
        template_service: TemplateService,
        damage_config: Dict,
    ):
        self.uid = uid
        self.template_service = template_service
        # 因为需要替换线上 enka 图片地址为本地地址，先克隆数据，避免修改原数据
        self.enka_data = enka_data
        self.avatar_id = avatar_id
        self.damage_config = damage_config

    async def render(self):
        character, weapon, artifacts = enka_parser(self.enka_data, self.avatar_id)
        character_name = character.name
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
        locale = assets.locale.get("zh-cn")
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

        data = {"uid": mask_number(self.uid), "character": character, "damage_info": damage, "locale": locale}

        return await self.template_service.render(
            "genshin/damage/damage.jinja2",
            data,
            full_page=True,
            ttl=7 * 24 * 60 * 60,
        )

    async def debug_render(self):
        character, weapon, artifacts = enka_parser(self.enka_data, self.avatar_id)
        character_info = assets.character.get(character.name)
        locale = assets.locale.get("zh-cn")
        skill_maps = []
        skill_maps.extend(character_info.get("skill_map1"))
        skill_maps.extend(character_info.get("skill_map2"))
        skill_maps.extend(character_info.get("skill_map3"))
        damage = []
        for skill_map in skill_maps:
            index = skill_map.get("index")
            skill = SkillInfo(index=index, config={"HuTao": {"after_e": True}})
            calculator_config = CalculatorConfig(character=character, weapon=weapon, artifacts=artifacts, skill=skill)
            damage_analysis = get_damage_analysis(calculator_config)
            if damage_analysis.normal is not None:
                damage_info = {"damage": damage_analysis, "skill_map": skill_map}
                damage.append(damage_info)

        data = {"uid": mask_number(self.uid), "character": character, "damage_info": damage, "locale": locale}

        return await self.template_service.render(
            "genshin/damage/damage_debug.jinja2",
            data,
            full_page=True,
            ttl=7 * 24 * 60 * 60,
        )
