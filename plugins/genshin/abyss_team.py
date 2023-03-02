from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, filters
from telegram.helpers import create_deep_linked_url

from core.dependence.assets import AssetsService
from core.plugin import Plugin, handler
from core.services.template.services import TemplateService
from metadata.shortname import roleToId
from modules.apihelper.client.components.abyss import AbyssTeam as AbyssTeamClient
from plugins.tools.genshin import GenshinHelper, CookiesNotFoundError, PlayerNotFoundError
from utils.log import logger

__all__ = ("AbyssTeamPlugin",)


class AbyssTeamPlugin(Plugin):
    """深境螺旋推荐配队查询"""

    def __init__(
        self,
        template: TemplateService,
        helper: GenshinHelper,
        assets_service: AssetsService,
    ):
        self.template_service = template
        self.helper = helper
        self.team_data = AbyssTeamClient()
        self.assets_service = assets_service

    @handler.command("abyss_team", block=False)
    @handler.message(filters.Regex("^深渊推荐配队(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 查深渊推荐配队命令请求", user.full_name, user.id)

        try:
            client = await self.helper.get_genshin_client(user.id)
        except (CookiesNotFoundError, PlayerNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            if filters.ChatType.GROUPS.filter(message):
                reply_message = await message.reply_text(
                    "未查询到您所绑定的账号信息，请先私聊派蒙绑定账号", reply_markup=InlineKeyboardMarkup(buttons)
                )
                self.add_delete_message_job(reply_message, delay=30)
                self.add_delete_message_job(message, delay=30)
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
