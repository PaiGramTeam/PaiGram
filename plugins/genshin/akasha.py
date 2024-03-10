from typing import TYPE_CHECKING, Optional

from telegram.constants import ChatAction
from telegram.ext import filters

from core.dependence.assets import AssetsService
from core.plugin import Plugin, handler
from core.services.template.models import FileType
from core.services.template.services import TemplateService
from gram_core.services.players import PlayersService
from metadata.genshin import AVATAR_DATA
from metadata.shortname import roleToName, roleToId
from modules.apihelper.client.components.akasha import Akasha
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class AkashaPlugin(Plugin):
    """Akasha 数据排行"""

    def __init__(
        self,
        assets_service: AssetsService = None,
        template_service: TemplateService = None,
        player_service: PlayersService = None,
    ) -> None:
        self.assets_service = assets_service
        self.template_service = template_service
        self.player_service = player_service

    async def get_user_uid(self, user_id: int) -> Optional[int]:
        player = await self.player_service.get(user_id)
        if player is None:
            return None
        return player.player_id

    @staticmethod
    async def get_leaderboard_data(character_id: int, uid: int = None):
        akasha = Akasha()
        categories = await akasha.get_leaderboard_categories(character_id)
        if len(categories) == 0 or len(categories[0].weapons) == 0:
            raise NotImplementedError
        calculation_id = categories[0].weapons[0].calculationId
        count = categories[0].count
        data = await akasha.get_leaderboard(calculation_id)
        if len(data) == 0:
            raise NotImplementedError
        user_data = []
        if uid:
            user_data = await akasha.get_leaderboard(calculation_id, uid)
        if len(user_data) == 0:
            data = [data]
        else:
            data = [user_data, data]
        return data, count

    async def get_avatar_board_render_data(self, character: str, uid: int):
        character_id = roleToId(character)
        if not character_id:
            raise NotImplementedError
        try:
            name_card = (await self.assets_service.namecard(character_id).navbar()).as_uri()
            avatar = (await self.assets_service.avatar(character_id).icon()).as_uri()
        except KeyError:
            logger.warning("未找到角色 %s 的角色名片/头像", character_id)
            name_card = None
            avatar = None
        rarity = 5
        try:
            rarity = {k: v["rank"] for k, v in AVATAR_DATA.items()}[str(character_id)]
        except KeyError:
            logger.warning("未找到角色 %s 的星级", character_id)
        akasha_data, count = await self.get_leaderboard_data(character_id, uid)
        return {
            "character": character,  # 角色名
            "avatar": avatar,  # 角色头像
            "namecard": name_card,  # 角色名片
            "rarity": rarity,  # 角色稀有度
            "count": count,
            "all_data": akasha_data,
        }

    @handler.command("avatar_board", block=False)
    @handler.message(filters.Regex(r"^角色排名(.*)$"), block=False)
    async def avatar_board(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        args = self.get_args(context)
        if len(args) == 0:
            reply_message = await message.reply_text("请指定要查询的角色")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        avatar_name = roleToName(args[0])
        uid = await self.get_user_uid(user_id)
        try:
            render_data = await self.get_avatar_board_render_data(avatar_name, uid)
        except NotImplementedError:
            reply_message = await message.reply_text("暂不支持该角色，或者角色名称错误")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message)
                self.add_delete_message_job(reply_message)
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)

        image = await self.template_service.render(
            "genshin/akasha/char_rank.jinja2",
            render_data,
            viewport={"width": 1040, "height": 500},
            full_page=True,
            query_selector=".container",
            file_type=FileType.PHOTO,
            ttl=24 * 60 * 60,
        )
        await image.reply_photo(message)
