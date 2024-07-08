import asyncio
import math
from typing import List, Optional, Sequence, TYPE_CHECKING, Union, Tuple, Any, Dict

from arkowrapper import ArkoWrapper
from simnet import GenshinClient
from simnet.errors import BadRequest as SimnetBadRequest
from simnet.models.genshin.calculator import CalculatorTalent, CalculatorCharacterDetails
from simnet.models.genshin.chronicle.characters import Character
from telegram.constants import ChatAction
from telegram.ext import filters

from core.config import config
from core.dependence.assets import AssetsService
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

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from gram_core.services.template.models import RenderResult

MAX_AVATAR_COUNT = 40


def parse_element(msg: str) -> set[Element]:
    elements = set()
    for element in Element:
        if element.value in msg:
            elements.add(element)
    return elements


def parse_weapon_type(msg: str) -> set[WeaponType]:
    weapon_types = set()
    for weapon_type in WeaponType:
        if weapon_type.value in msg:
            weapon_types.add(weapon_type)
    return weapon_types


class TooManyRequests(Exception):
    """请求过多"""


class SkillData(Model):
    """天赋数据"""

    skill: CalculatorTalent
    buffed: bool = False
    """是否得到了命座加成"""


class AvatarData(Model):
    avatar: Character
    detail: CalculatorCharacterDetails
    icon: str
    weapon: Optional[str]
    skills: List[SkillData]

    def sum_of_skills(self) -> int:
        total_level = 0
        for skill_data in self.skills:
            total_level += skill_data.skill.level
        return total_level


class AvatarListPlugin(Plugin):
    """练度统计"""

    def __init__(
        self,
        player_service: PlayersService = None,
        cookies_service: CookiesService = None,
        assets_service: AssetsService = None,
        template_service: TemplateService = None,
        helper: GenshinHelper = None,
        character_details: CharacterDetails = None,
        player_info_service: PlayerInfoService = None,
        player_info_system: PlayerInfoSystem = None,
    ) -> None:
        self.cookies_service = cookies_service
        self.assets_service = assets_service
        self.template_service = template_service
        self.helper = helper
        self.character_details = character_details
        self.player_service = player_service
        self.player_info_service = player_info_service
        self.player_info_system = player_info_system

    async def get_avatar_data(self, character: Character, client: "GenshinClient") -> Optional["AvatarData"]:
        detail = await self.character_details.get_character_details(client, character)
        if detail is None:
            return None
        if character.id == 10000005:  # 针对男草主
            talents = []
            for talent in detail.talents:
                if "普通攻击" in talent.name:
                    talent.Config.allow_mutation = True
                    # noinspection Pydantic
                    talent.group_id = 1131
                if talent.type in ["attack", "skill", "burst"]:
                    talents.append(talent)
        else:
            talents = [t for t in detail.talents if t.type in ["attack", "skill", "burst"]]
        buffed_talents = []
        for constellation in filter(lambda x: x.pos in [3, 5], character.constellations[: character.constellation]):
            if result := list(
                filter(lambda x: all([x.name in constellation.effect]), talents)  # pylint: disable=W0640
            ):
                buffed_talents.append(result[0].type)
        return AvatarData(
            avatar=character,
            detail=detail,
            icon=(await self.assets_service.avatar(character.id).side()).as_uri(),
            weapon=(
                await self.assets_service.weapon(character.weapon.id).__getattr__(
                    "icon" if character.weapon.ascension < 2 else "awaken"
                )()
            ).as_uri(),
            skills=[
                SkillData(skill=s, buffed=s.type in buffed_talents)
                for s in sorted(talents, key=lambda x: ["attack", "skill", "burst"].index(x.type))
            ],
        )

    async def get_avatars_data(
        self, characters: Sequence[Character], client: "GenshinClient", max_length: int = None
    ) -> List["AvatarData"]:
        async def _task(c):
            return await self.get_avatar_data(c, client)

        task_results = await asyncio.gather(*[_task(character) for character in characters])

        return sorted(
            list(filter(lambda x: x, task_results)),
            key=lambda x: (
                x.avatar.level,
                x.avatar.rarity,
                x.sum_of_skills(),
                x.avatar.constellation,
                # TODO 如果加入武器排序条件，需要把武器转化为图片url的处理后置
                # x.weapon.level,
                # x.weapon.rarity,
                # x.weapon.refinement,
                x.avatar.friendship,
            ),
            reverse=True,
        )[:max_length]

    async def avatar_list_render(
        self,
        base_render_data: Dict,
        avatar_datas: List[AvatarData],
        only_one_page: bool,
    ) -> Union[Tuple[Any], List["RenderResult"], None]:
        def render_task(start_id: int, c: List[AvatarData]):
            _render_data = {
                "avatar_datas": c,  # 角色数据
                "start_id": start_id,  # 开始序号
            }
            _render_data.update(base_render_data)
            return self.template_service.render(
                "genshin/avatar_list/main.jinja2",
                _render_data,
                viewport={"width": 1040, "height": 500},
                full_page=True,
                query_selector=".container",
                file_type=FileType.PHOTO,
                ttl=30 * 24 * 60 * 60,
            )

        if only_one_page:
            return [await render_task(0, avatar_datas)]
        image_count = len(avatar_datas)
        while image_count > MAX_AVATAR_COUNT:
            image_count /= 2
        image_count = math.ceil(image_count)
        avatar_datas_group = [avatar_datas[i : i + image_count] for i in range(0, len(avatar_datas), image_count)]
        tasks = [render_task(i * image_count, c) for i, c in enumerate(avatar_datas_group)]
        return await asyncio.gather(*tasks)

    async def render(
        self,
        client: "GenshinClient",
        user_id: int,
        user_name: str,
        all_avatars: bool = False,
        filter_elements: set[Element] = None,
        filter_weapon_types: set[WeaponType] = None,
    ) -> List["RenderResult"]:
        characters = await client.get_genshin_characters(client.player_id)
        if filter_elements:
            characters = [c for c in characters if c.element in {element.name for element in filter_elements}]
        if filter_weapon_types:
            characters = [c for c in characters if WeaponType(c.weapon.type) in filter_weapon_types]
        avatar_datas: List[AvatarData] = await self.get_avatars_data(
            characters, client, None if all_avatars else MAX_AVATAR_COUNT
        )
        if not avatar_datas:
            raise TooManyRequests()
        name_card, avatar, nickname, rarity = await self.player_info_system.get_player_info(
            client.player_id, user_id, user_name
        )
        base_render_data = {
            "uid": mask_number(client.player_id),  # 玩家uid
            "nickname": nickname,  # 玩家昵称
            "avatar": avatar,  # 玩家头像
            "rarity": rarity,  # 玩家头像对应的角色星级
            "namecard": name_card,  # 玩家名片
            "has_more": len(characters) != len(avatar_datas),  # 是否显示了全部角色
        }

        return await self.avatar_list_render(base_render_data, avatar_datas, not all_avatars)

    @handler.command("avatars", cookie=True, block=False)
    @handler.message(filters.Regex(r"^(全部)?练度统计$"), cookie=True, block=False)
    async def avatar_list(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        user_name = self.get_real_user_name(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        all_avatars = "全部" in message.text or "all" in message.text  # 是否发送全部角色
        filter_elements = parse_element(message.text)
        filter_weapon_types = parse_weapon_type(message.text)

        self.log_user(
            update,
            logger.info,
            "[bold]练度统计[/bold]: all=%s, filter_elements=%s, filter_weapon_types=%s",
            all_avatars,
            filter_elements,
            filter_weapon_types,
            extra={"markup": True},
        )

        try:
            async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
                notice = await message.reply_text(f"{config.notice.bot_name}需要收集整理数据，还请耐心等待哦~")
                self.add_delete_message_job(notice, delay=60)
                await message.reply_chat_action(ChatAction.TYPING)
                images = await self.render(
                    client, user_id, user_name, all_avatars, filter_elements, filter_weapon_types
                )
        except TooManyRequests:
            reply_message = await message.reply_html("服务器熟啦 ~ 请稍后再试")
            self.add_delete_message_job(reply_message, delay=20)
            return
        except SimnetBadRequest as e:
            if e.ret_code == -502002:
                reply_message = await message.reply_html("请先在米游社中使用一次<b>养成计算器</b>后再使用此功能~")
                self.add_delete_message_job(reply_message, delay=20)
                return
            raise e

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

        try:
            async with self.helper.genshin(user_id, player_id=uid) as client:
                images = await self.render(client, user_id, user_name)
                render = images[0]
        except TooManyRequests:
            await callback_query.answer("服务器熟啦 ~ 请稍后再试", show_alert=True)
            return
        except SimnetBadRequest as e:
            if e.ret_code == -502002:
                await callback_query.answer("请先在米游社中使用一次养成计算器后再使用此功能~", show_alert=True)
                return
            raise e
        await render.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="练度统计",
                hash="avatar_list",
                callback=self.avatar_list_use_by_inline,
                cookie=True,
                player=True,
            )
        ]
