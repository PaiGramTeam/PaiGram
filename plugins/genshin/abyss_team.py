from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters
from telegram.helpers import create_deep_linked_url

from core.base.assets import AssetsService
from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.template import TemplateService
from core.user import UserService
from core.user.error import UserNotFoundError
from metadata.shortname import roleToId
from modules.apihelper.client.components.abyss import AbyssTeam as AbyssTeamClient
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
        self.team_data = AbyssTeamClient()

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
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号", reply_markup=InlineKeyboardMarkup(buttons))
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
        render_result = await self.template_service.render(
            "genshin/abyss_team/abyss_team.html",
            abyss_teams_data,
            {"width": 785, "height": 800},
            full_page=True,
            query_selector=".bg-contain",
        )
        await render_result.reply_photo(message, filename=f"abyss_team_{user.id}.png", allow_sending_without_reply=True)
