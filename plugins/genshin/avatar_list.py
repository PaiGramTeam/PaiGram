"""练度统计"""
import asyncio
from typing import List, Optional, Sequence

from aiohttp import ClientConnectorError
from arkowrapper import ArkoWrapper
from enkanetwork import Assets as EnkaAssets, EnkaNetworkAPI, VaildateUIDError, HTTPException, EnkaPlayerNotFound
from genshin import Client, GenshinException, InvalidCookies
from genshin.models import CalculatorCharacterDetails, CalculatorTalent, Character
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters
from telegram.helpers import create_deep_linked_url

from core.config import config
from core.dependence.assets import AssetsService
from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from metadata.genshin import AVATAR_DATA, NAMECARD_DATA
from modules.wiki.base import Model
from plugins.tools.genshin import CookiesNotFoundError, GenshinHelper, PlayerNotFoundError, CharacterDetails
from utils.enkanetwork import RedisCache
from utils.log import logger
from utils.patch.aiohttp import AioHttpTimeoutException


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
    def __init__(
        self,
        cookies_service: CookiesService = None,
        assets_service: AssetsService = None,
        template_service: TemplateService = None,
        redis: RedisDB = None,
        helper: GenshinHelper = None,
        character_details: CharacterDetails = None,
    ) -> None:
        self.cookies_service = cookies_service
        self.assets_service = assets_service
        self.template_service = template_service
        self.enka_client = EnkaNetworkAPI(lang="chs", user_agent=config.enka_network_api_agent)
        self.enka_client.set_cache(RedisCache(redis.client, key="plugin:avatar_list:enka_network", ttl=60 * 60 * 3))
        self.enka_assets = EnkaAssets(lang="chs")
        self.helper = helper
        self.character_details = character_details

    async def get_user_client(self, update: Update, context: CallbackContext) -> Optional[Client]:
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
        detail = await self.character_details.get_character_details(client,character)
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

    async def get_final_data(self, client: Client, characters: Sequence[Character], update: Update):
        try:
            response = await self.enka_client.fetch_user(client.uid, info=True)
            name_card = (await self.assets_service.namecard(response.player.namecard.id).navbar()).as_uri()
            avatar = (await self.assets_service.avatar(response.player.avatar.id).icon()).as_uri()
            nickname = response.player.nickname
            if response.player.avatar.id in [10000005, 10000007]:
                rarity = 5
            else:
                rarity = {k: v["rank"] for k, v in AVATAR_DATA.items()}[str(response.player.avatar.id)]
            return name_card, avatar, nickname, rarity
        except (VaildateUIDError, EnkaPlayerNotFound, HTTPException) as exc:
            logger.warning("EnkaNetwork 请求失败: %s", str(exc))
        except (AioHttpTimeoutException, ClientConnectorError) as exc:
            logger.warning("EnkaNetwork 请求超时: %s", str(exc))
        except Exception as exc:
            logger.error("EnkaNetwork 请求失败: %s", exc_info=exc)
        choices = ArkoWrapper(characters).filter(lambda x: x.friendship == 10)  # 筛选出好感满了的角色
        if choices.length == 0:  # 若没有满好感角色、则以好感等级排序
            choices = ArkoWrapper(characters).sort(lambda x: x.friendship, reverse=True)
        name_card_choices = (  # 找到与角色对应的满好感名片ID
            ArkoWrapper(choices)
            .map(lambda x: next(filter(lambda y: y["name"].split("·")[0] == x.name, NAMECARD_DATA.values()), None))
            .filter(lambda x: x)
            .map(lambda x: int(x["id"]))
        )
        # noinspection PyTypeChecker
        name_card = (await self.assets_service.namecard(name_card_choices[0]).navbar()).as_uri()
        avatar = (await self.assets_service.avatar(cid := choices[0].id).icon()).as_uri()
        nickname = update.effective_user.full_name
        if cid in [10000005, 10000007]:
            rarity = 5
        else:
            rarity = {k: v["rank"] for k, v in AVATAR_DATA.items()}[str(cid)]
        return name_card, avatar, nickname, rarity

    async def get_default_final_data(self, characters: Sequence[Character], update: Update):
        nickname = update.effective_user.full_name
        rarity = 5
        # 须弥·正明
        name_card = (await self.assets_service.namecard(210132).navbar()).as_uri()
        if traveller := next(filter(lambda x: x.id in [10000005, 10000007], characters), None):
            avatar = (await self.assets_service.avatar(traveller.id).icon()).as_uri()
        else:
            avatar = (await self.assets_service.avatar(10000005).icon()).as_uri()
        return name_card, avatar, nickname, rarity

    @handler.command("avatars", filters.Regex(r"^/avatars\s*(?:(\d+)|(all))?$"), block=False)
    @handler.message(filters.Regex(r"^(全部)?练度统计$"), block=False)
    async def avatar_list(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message

        args = [i.lower() for i in context.match.groups() if i]

        all_avatars = any(["all" in args, "全部" in args])  # 是否发送全部角色

        logger.info("用户 %s[%s] [bold]练度统计[/bold]: all=%s", user.full_name, user.id, all_avatars, extra={"markup": True})

        client = await self.get_user_client(user, message, context)
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

        try:
            name_card, avatar, nickname, rarity = await self.get_final_data(client, characters, update)
        except Exception as exc:  # pylint: disable=W0703
            logger.error("卡片信息请求失败 %s", str(exc))
            name_card, avatar, nickname, rarity = await self.get_default_final_data(characters, update)

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
