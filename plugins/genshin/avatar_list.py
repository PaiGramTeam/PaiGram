import asyncio
from collections.abc import Sequence
import math
import typing

from arkowrapper import ArkoWrapper
from simnet import GenshinClient
from simnet.models.genshin.chronicle.character_detail import (
    CharacterSkill,
    GenshinDetailCharacter,
)
from simnet.models.genshin.chronicle.characters import Character
from telegram.constants import ChatAction
from telegram.ext import filters

from core.config import config
from core.dependence.assets.impl.genshin import AssetsService
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.players.services import PlayerInfoService
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from gram_core.services.template.models import RenderGroupResult
from modules.wiki.base import Model
from modules.wiki.other import Element, WeaponType
from plugins.tools.genshin import CharacterDetails, GenshinHelper
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger
from utils.uid import mask_number

if typing.TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from gram_core.services.template.models import RenderResult

MAX_AVATAR_COUNT = 40


def parse_element(msg: str) -> set[Element]:
    return {element for element in Element if element.value in msg}


def parse_weapon_type(msg: str) -> set[WeaponType]:
    return {weapon_type for weapon_type in WeaponType if weapon_type.value in msg}


class TooManyRequests(Exception):
    """请求过多"""


class PlayerData(Model):
    """角色信息，如头像、名片等"""

    player_id: int
    name_card: str
    avatar: str
    nickname: str
    rarity: int


class SkillData(Model):
    """天赋数据"""

    skill: CharacterSkill
    buffed: bool = False
    """是否得到了命座加成"""
    tartaglia_buffed: bool = False
    """是否得到了达达利亚加成"""

    @property
    def max_level(self) -> int:
        """不含命座增益的技能满级等级"""
        max_level = 10
        if self.buffed:
            max_level += 3
        if self.tartaglia_buffed:
            max_level += 1
        return max_level


class AvatarData(Model):
    avatar: GenshinDetailCharacter
    icon: str
    weapon: str | None
    skills: list[SkillData]

    def sum_of_skills(self) -> int:
        return sum(skill.skill.level for skill in self.skills)


class AvatarListPlugin(Plugin):
    """练度统计"""

    def __init__(
        self,
        player_service: PlayersService,
        cookies_service: CookiesService,
        assets_service: AssetsService,
        template_service: TemplateService,
        helper: GenshinHelper,
        character_details: CharacterDetails,
        player_info_service: PlayerInfoService,
        player_info_system: PlayerInfoSystem,
    ) -> None:
        self.cookies_service: CookiesService = cookies_service
        self.assets_service: AssetsService = assets_service
        self.template_service: TemplateService = template_service
        self.helper: GenshinHelper = helper
        self.character_details: CharacterDetails = character_details
        self.player_service: PlayersService = player_service
        self.player_info_service: PlayerInfoService = player_info_service
        self.player_info_system: PlayerInfoSystem = player_info_system

    async def get_avatar_data(self, chara: GenshinDetailCharacter) -> AvatarData:
        """
        将角色、技能、武器详情打包为 AvatarData
        主要在获取图标
        """
        # 获取普攻、战技、爆发天赋等级以及确认是否带有三命、五命带来的等级提升
        active_constellations = [
            constellation.effect
            for constellation in chara.constellations
            if constellation.activated and constellation.pos in (3, 5)
        ]
        skills = [
            SkillData(
                skill=skill,
                buffed=any(skill.name in effect for effect in active_constellations),
                # 达达利亚天赋「诸武精通」会导致 API 返回的达达利亚「普通攻击·断雨」技能等级 +1
                # 目前只有 1.1 角色达达利亚有这种效果，让我们祈祷未来不会有新的这种天赋技能
                tartaglia_buffed=(skill.id == 10331),
            )
            for skill in chara.skills
            # skill_type == 1 表示该技能为普攻、战技、爆发或者替代冲刺的一种
            # 排除的两个是绫华和莫娜的替代冲刺技能，它们的 skill_type 也是 1，缺少技能类型字段，只好特判一下
            # 不能直接判断效果文案中是否存在「替代冲刺」，因为流浪者的元素战技效果文案中也有「替代冲刺」
            if skill.skill_type == 1 and skill.id not in (10013, 10413)
        ]
        # 获取角色头像图标和武器图标
        avatar_path = self.assets_service.avatar.side(chara.base.id)
        avatar_uri = avatar_path.as_uri() if avatar_path else ""
        weapon_path = self.assets_service.weapon.icon(chara.weapon.id) if chara.weapon.ascension < 2 else self.assets_service.weapon.awaken(chara.weapon.id)
        weapon_uri = weapon_path.as_uri() if weapon_path else ""
        return AvatarData(avatar=chara, skills=skills, icon=avatar_uri, weapon=weapon_uri)

    async def get_avatar_datas(self, characters: Sequence[Character], client: GenshinClient) -> list["AvatarData"]:
        character_ids = [character.id for character in characters]
        details = await client.get_genshin_character_detail(character_ids)
        avatar_tasks = [self.get_avatar_data(chara) for chara in details.characters]
        avatars = await asyncio.gather(*avatar_tasks)
        avatars.sort(
            reverse=True,
            key=lambda avatar: (
                avatar.avatar.base.level,  # 角色等级
                avatar.avatar.base.rarity,  # 角色星级
                avatar.sum_of_skills(),  # 角色技能等级之和
                avatar.avatar.base.constellation,  # 角色命座
                avatar.avatar.base.friendship,  # 角色好感等级
                avatar.avatar.weapon.level,  # 角色武器等级
                avatar.avatar.weapon.rarity,  # 角色武器星级
                avatar.avatar.weapon.refinement,  # 角色武器精炼
            ),
        )
        return avatars

    async def avatar_list_render(
        self,
        base_render_data: dict[str, str | int | bool],
        avatar_datas: list[AvatarData],
        only_one_page: bool,
    ) -> list["RenderResult"]:
        async def render_task(start_id: int, c: list[AvatarData]):
            _render_data: dict[str, str | int | bool | list[AvatarData]] = {
                "avatar_datas": c,  # 角色数据
                "start_id": start_id,  # 开始序号
            }
            _render_data.update(base_render_data)
            return await self.template_service.render(
                "genshin/avatar_list/main.jinja2",
                _render_data,
                viewport={"width": 1040, "height": 500},
                full_page=True,
                query_selector=".container",
                file_type=FileType.PHOTO,
                ttl=30 * 24 * 60 * 60,
            )

        if only_one_page:
            return [await render_task(0, avatar_datas[:MAX_AVATAR_COUNT])]
        image_count = len(avatar_datas)
        while image_count > MAX_AVATAR_COUNT:
            image_count /= 2
        image_count = math.ceil(image_count)
        avatar_datas_group = [avatar_datas[i : i + image_count] for i in range(0, len(avatar_datas), image_count)]
        tasks = [render_task(i * image_count, c) for i, c in enumerate(avatar_datas_group)]
        return await asyncio.gather(*tasks)

    async def render(
        self, avatar_datas: list[AvatarData], player_data: PlayerData, show_all: bool = False
    ) -> list["RenderResult"]:
        base_render_data = {
            "uid": mask_number(player_data.player_id),  # 玩家uid
            "nickname": player_data.nickname,  # 玩家昵称
            "avatar": player_data.avatar,  # 玩家头像
            "rarity": player_data.rarity,  # 玩家头像对应的角色星级
            "namecard": player_data.name_card,  # 玩家名片
            "has_more": not show_all and len(avatar_datas) > MAX_AVATAR_COUNT,  # 是否显示了全部角色
        }
        return await self.avatar_list_render(base_render_data, avatar_datas, not show_all)

    @handler.command("avatars", cookie=True, block=False)
    @handler.message(filters.Regex(r"^(全部)?练度统计$"), cookie=True, block=False)
    async def avatar_list(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        user_name = self.get_real_user_name(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        show_all = "全部" in message.text or "all" in message.text  # 是否发送全部角色
        filter_elements = parse_element(message.text)
        filter_weapon_types = parse_weapon_type(message.text)

        self.log_user(
            update,
            logger.info,
            "[bold]练度统计[/bold]: all=%s, filter_elements=%s, filter_weapon_types=%s",
            show_all,
            "".join(element.value for element in filter_elements),
            "、".join(weapon.value for weapon in filter_weapon_types),
            extra={"markup": True},
        )
        # 获取角色和武器详情数据
        async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
            notice = await message.reply_text(f"{config.notice.bot_name}需要收集整理数据，还请耐心等待哦~")
            self.add_delete_message_job(notice, delay=60)
            await message.reply_chat_action(ChatAction.TYPING)
            characters = await client.get_genshin_characters()
            if filter_elements:
                filter_element_names = {element.name for element in filter_elements}
                characters = [c for c in characters if c.element in filter_element_names]
            if filter_weapon_types:
                filter_weapon_type_names = {weapon_types.value for weapon_types in filter_weapon_types}
                characters = [c for c in characters if c.weapon.type in filter_weapon_type_names]
            if not characters:
                reply_message = await message.reply_text("没有符合条件的角色")
                self.add_delete_message_job(reply_message, delay=20)
                return
            avatar_datas: list[AvatarData] = await self.get_avatar_datas(characters, client)
        if not avatar_datas:
            reply_message = await message.reply_html("服务器熟啦 ~ 请稍后再试")
            self.add_delete_message_job(reply_message, delay=20)
            return
        (name_card, avatar, nickname, rarity) = await self.player_info_system.get_player_info(
            client.player_id, user_id, user_name
        )
        player_data = PlayerData(
            player_id=client.player_id, name_card=name_card, avatar=avatar, nickname=nickname, rarity=rarity
        )
        images = await self.render(avatar_datas, player_data, show_all)

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        for group in ArkoWrapper(images).group(10):  # 每 10 张图片分一个组
            await RenderGroupResult(results=group).reply_media_group(message, write_timeout=60)

        self.log_user(
            update,
            logger.info,
            "[bold]练度统计[/bold]发送图片成功",
            extra={"markup": True},
        )

    async def avatar_list_use_by_inline(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user_id = await self.get_real_user_id(update)
        user_name = self.get_real_user_name(update)
        uid = IInlineUseData.get_uid_from_context(context)
        self.log_user(update, logger.info, "查询练度统计")
        async with self.helper.genshin(user_id, player_id=uid) as client:
            characters = await client.get_genshin_characters()
            avatar_datas: list[AvatarData] = await self.get_avatar_datas(characters, client)
            (name_card, avatar, nickname, rarity) = await self.player_info_system.get_player_info(
                client.player_id, user_id, user_name
            )
            player_data = PlayerData(
                player_id=client.player_id, name_card=name_card, avatar=avatar, nickname=nickname, rarity=rarity
            )
        images = await self.render(avatar_datas, player_data)
        render = images[0]
        await render.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> list[IInlineUseData | None]:
        return [
            IInlineUseData(
                text="练度统计",
                hash="avatar_list",
                callback=self.avatar_list_use_by_inline,
                cookie=True,
                player=True,
            )
        ]
