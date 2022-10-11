from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user import UserService
from core.user.error import UserNotFoundError
from metadata.shortname import roleToId
from modules.apihelper.abyss_team import AbyssTeamData
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class AbyssTeam(Plugin, BasePlugin):
    """深境螺旋推荐配队查询"""

    def __init__(
        self, user_service: UserService = None, template_service: TemplateService = None, assets: AssetsService = None
    ):
        self.template_service = template_service
        self.user_service = user_service
        self.assets_service = assets
        self.team_data = AbyssTeamData()

    @handler(CommandHandler, command="abyss_team", block=False)
    @handler(MessageHandler, filters=filters.Regex("^深渊推荐配队(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 查深渊推荐配队命令请求")

        try:
            client = await get_genshin_client(user.id)
        except (CookiesNotFoundError, UserNotFoundError):
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 10)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
            return

        await message.reply_chat_action(ChatAction.TYPING)
        team_data = await self.team_data.get_data()
        # 尝试获取用户已绑定的原神账号信息
        characters = await client.get_genshin_characters(client.uid)
        user_data = [character.name for character in characters]
        team_data.sort(user_data)
        random_team = team_data.random_team()
        abyss_teams_data = {"uid": client.uid, "version": team_data.version, "teams": []}
        for i in random_team:
            team = {
                "up": [],
                "up_rate": f"{i.up.rate * 100: .2f}%",
                "down": [],
                "down_rate": f"{i.down.rate * 100: .2f}%",
            }

            for lane in ["up", "down"]:
                for member in getattr(i, lane).formation:
                    name = member.name
                    temp = {
                        "icon": (await self.assets_service.avatar(roleToId(name.replace("旅行者", "空"))).icon()).as_uri(),
                        "name": name,
                        "star": member.star,
                        "hava": (name in user_data) if user_data else True,
                    }
                    team[lane].append(temp)

            abyss_teams_data["teams"].append(team)

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        png_data = await self.template_service.render(
            "genshin/abyss_team/abyss_team.html",
            abyss_teams_data,
            {"width": 785, "height": 800},
            full_page=True,
            query_selector=".bg-contain",
        )
        await message.reply_photo(png_data, filename=f"abyss_team_{user.id}.png", allow_sending_without_reply=True)
