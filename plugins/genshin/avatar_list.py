import asyncio
from typing import List, Optional, Sequence, TYPE_CHECKING

from genshin import Client, GenshinException, InvalidCookies
from genshin.models import CalculatorCharacterDetails, CalculatorTalent, Character
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.dependence.assets import AssetsService
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.players.services import PlayerInfoService
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from metadata.genshin import AVATAR_DATA
from modules.wiki.base import Model
from plugins.tools.genshin import CookiesNotFoundError, GenshinHelper, PlayerNotFoundError, CharacterDetails
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import ContextTypes
    from telegram import Update, User


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
    ) -> None:
        self.cookies_service = cookies_service
        self.assets_service = assets_service
        self.template_service = template_service
        self.helper = helper
        self.character_details = character_details
        self.player_service = player_service
        self.player_info_service = player_info_service

    async def get_user_client(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> Optional[Client]:
        message = update.effective_message
        user = update.effective_user
        try:
            return await self.helper.get_genshin_client(user.id)
        except PlayerNotFoundError:  # 若未找到账号
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
        except CookiesNotFoundError:
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙绑定账号",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            else:
                await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙进行绑定",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons),
                )

    async def get_avatar_data(self, character: Character, client: Client) -> Optional["AvatarData"]:
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
        self, characters: Sequence[Character], client: Client, max_length: int = None
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

    async def get_final_data(self, player_id: int, user: "User"):
        player = await self.player_service.get(user.id, player_id)
        player_info = await self.player_info_service.get(player)
        nickname = user.full_name
        name_card: Optional[str] = None
        avatar: Optional[str] = None
        rarity: int = 5
        try:
            if player_info is not None:
                if player_info.nickname is not None:
                    nickname = player_info.nickname
                if player_info.name_card is not None:
                    name_card = (await self.assets_service.namecard(int(player_info.name_card)).navbar()).as_uri()
                if player_info.hand_image is not None:
                    avatar = (await self.assets_service.avatar(player_info.hand_image).icon()).as_uri()
                    try:
                        rarity = {k: v["rank"] for k, v in AVATAR_DATA.items()}[player_info.hand_image]
                    except KeyError:
                        logger.warning("未找到角色 %s 的星级", player_info.hand_image)
        except Exception as exc:  # pylint: disable=W0703
            logger.error("卡片信息请求失败 %s", str(exc))
        if name_card is not None:  # 默认
            name_card = (await self.assets_service.namecard(210001).navbar()).as_uri()
        return name_card, avatar, nickname, rarity

    @handler.command("avatars", filters.Regex(r"^/avatars\s*(?:(\d+)|(all))?$"), block=False)
    @handler.message(filters.Regex(r"^(全部)?练度统计$"), block=False)
    async def avatar_list(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        message = update.effective_message

        args = [i.lower() for i in context.match.groups() if i]

        all_avatars = any(["all" in args, "全部" in args])  # 是否发送全部角色

        logger.info("用户 %s[%s] [bold]练度统计[/bold]: all=%s", user.full_name, user.id, all_avatars, extra={"markup": True})

        client = await self.get_user_client(update, context)
        if not client:
            return

        notice = await message.reply_text("派蒙需要收集整理数据，还请耐心等待哦~")
        await message.reply_chat_action(ChatAction.TYPING)

        try:
            characters = await client.get_genshin_characters(client.uid)
            avatar_datas: List[AvatarData] = await self.get_avatars_data(
                characters, client, None if all_avatars else 20
            )
        except InvalidCookies as exc:
            await notice.delete()
            await client.get_genshin_user(client.uid)
            logger.warning("用户 %s[%s] 无法请求角色数数据 API返回信息为 [%s]%s", user.full_name, user.id, exc.retcode, exc.original)
            reply_message = await message.reply_text("出错了呜呜呜 ~ 当前访问令牌无法请求角色数数据，请尝试重新获取Cookie。")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
            return
        except GenshinException as e:
            await notice.delete()
            if e.retcode == -502002:
                reply_message = await message.reply_html("请先在米游社中使用一次<b>养成计算器</b>后再使用此功能~")
                self.add_delete_message_job(reply_message, delay=20)
                return
            raise e

        name_card, avatar, nickname, rarity = await self.get_final_data(client.uid, user)

        render_data = {
            "uid": client.uid,  # 玩家uid
            "nickname": nickname,  # 玩家昵称
            "avatar": avatar,  # 玩家头像
            "rarity": rarity,  # 玩家头像对应的角色星级
            "namecard": name_card,  # 玩家名片
            "avatar_datas": avatar_datas,  # 角色数据
            "has_more": len(characters) != len(avatar_datas),  # 是否显示了全部角色
        }

        as_document = all_avatars and len(characters) > 20

        await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT if as_document else ChatAction.UPLOAD_PHOTO)

        image = await self.template_service.render(
            "genshin/avatar_list/main.html",
            render_data,
            viewport={"width": 1040, "height": 500},
            full_page=True,
            query_selector=".container",
            file_type=FileType.DOCUMENT if as_document else FileType.PHOTO,
            ttl=30 * 24 * 60 * 60,
        )
        self.add_delete_message_job(notice, delay=5)
        if as_document:
            await image.reply_document(message, filename="练度统计.png")
        else:
            await image.reply_photo(message)

        logger.info(
            "用户 %s[%s] [bold]练度统计[/bold]发送%s成功",
            user.full_name,
            user.id,
            "文件" if all_avatars else "图片",
            extra={"markup": True},
        )
