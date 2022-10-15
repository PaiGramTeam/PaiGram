"""练度统计"""
from typing import Iterable, List

from arkowrapper import ArkoWrapper
from enkanetwork import Assets as EnkaAssets, EnkaNetworkAPI
from genshin.models import CalculatorCharacterDetails, CalculatorTalent, Character
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.config import config
from core.cookies.error import CookiesNotFoundError
from core.cookies.services import CookiesService
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user.error import UserNotFoundError
from metadata.genshin import NAMECARD_DATA
from modules.wiki.base import Model
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger

api = "https://api-takumi.mihoyo.com/event/e20200928calculate/v1/sync/avatar/detail"


class AvatarListPlugin(Plugin, BasePlugin):
    def __init__(
        self, cookies_service: CookiesService, assets_service: AssetsService, template_service: TemplateService
    ) -> None:
        self.cookies_service = cookies_service
        self.assets_service = assets_service
        self.template_service = template_service
        self.enka_client = EnkaNetworkAPI(lang="chs", agent=config.enka_network_api_agent)
        self.enka_assets = EnkaAssets(lang="chs")

    @handler.command("avatars")
    @handler.message(filters.Regex(r"^练度统计$"))
    @restricts(30)
    @error_callable
    async def avatar_list(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message

        logger.info(f"用户 {user.full_name}[{user.id}] [bold]练度统计[/bold]", extra={"markup": True})

        try:
            client = await get_genshin_client(user.id)
        except UserNotFoundError:  # 若未找到账号
            if filters.ChatType.GROUPS.filter(message):
                buttons = [[InlineKeyboardButton("点我私聊", url=f"https://t.me/{context.bot.username}?start=set_uid")]]
                reply_msg = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_msg.chat_id, reply_msg.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先私聊派蒙绑定账号")
            return
        except CookiesNotFoundError:
            if filters.ChatType.GROUPS.filter(message):
                buttons = [[InlineKeyboardButton("点我私聊", url=f"https://t.me/{context.bot.username}?start=set_uid")]]
                reply_msg = await message.reply_text(
                    "此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙绑定账号",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
                self._add_delete_message_job(context, reply_msg.chat_id, reply_msg.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("此功能需要绑定<code>cookie</code>后使用，请先私聊派蒙进行绑定", parse_mode=ParseMode.HTML)
            return

        notice = await message.reply_text("派蒙需要收集整理数据，还请耐心等待哦~")
        await message.reply_chat_action(ChatAction.TYPING)

        characters = await client.get_genshin_characters(client.uid)

        avatar_datas: List[AvatarData] = []
        for character in characters:
            try:
                detail = await client.get_character_details(character)
            except RuntimeError:
                region = "cn_gf01" if str(client.uid)[0] in ["1", "2"] else "cn_qd01"
                detail = CalculatorCharacterDetails.parse_obj(
                    await client.request(api, params={"uid": client.uid, "region": region, "avatar_id": character.id})
                )
            talents = [t for t in detail.talents if t.type in ["attack", "skill", "burst"]]
            buffed_talents = []
            for constellation in filter(lambda x: x.pos in [3, 5], character.constellations[: character.constellation]):
                if result := list(
                    filter(lambda x: all([x.name in constellation.effect]), talents)
                ):  # pylint: disable=W0640
                    buffed_talents.append(result[0].type)
            avatar_datas.append(
                AvatarData(
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
            )

        try:
            response = await self.enka_client.fetch_user(client.uid)
            namecard = (await self.assets_service.namecard(response.player.namecard.id).navbar()).as_uri()
            avatar = (await self.assets_service.avatar(response.player.icon.id).icon()).as_uri()
            nickname = response.player.nickname
        except Exception as e:  # pylint: disable=W0703
            logger.debug(f"enka 请求失败: {e}")
            choices = ArkoWrapper(characters).filter(lambda x: x.friendship == 10)
            if not [choices]:
                choices = ArkoWrapper(characters).sort(lambda x: x.friendship, reverse=True)
            namecard_choices = (
                ArkoWrapper(choices)
                .map(lambda x: next(filter(lambda y: y["name"].split(".")[0] == x.name, NAMECARD_DATA.values()), None))
                .filter(lambda x: x)
                .map(lambda x: x["id"])
            )
            namecard = (await self.assets_service.namecard(namecard_choices[0]).navbar()).as_uri()
            avatar = (await self.assets_service.avatar(choices[0].id).icon()).as_uri()
            nickname = update.effective_user.full_name

        render_data = {
            "uid": client.uid,
            "nickname": nickname,
            "avatar": avatar,
            "namecard": namecard,
            "avatar_datas": avatar_datas,
        }

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        image = await self.template_service.render(
            "genshin/avatar_list/main.html", render_data, viewport={"width": 1040, "height": 500}, full_page=True
        )

        await message.reply_document(InputFile(image, filename=f"{user.full_name}的练度统计.png"))
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, notice.chat_id, notice.message_id, 10)


class SkillData(Model):
    skill: CalculatorTalent
    buffed: bool = False


class AvatarData(Model):
    avatar: Character
    detail: CalculatorCharacterDetails
    icon: str
    weapon: str
    skills: Iterable[SkillData]
