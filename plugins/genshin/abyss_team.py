from telegram import Update, User
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

    def __init__(self, user_service: UserService = None, template_service: TemplateService = None,
                 assets: AssetsService = None):
        self.template_service = template_service
        self.user_service = user_service
        self.assets_service = assets
        self.team_data = AbyssTeamData()

    @staticmethod
    def _get_role_star_bg(value: int):
        if value == 4:
            return "./../abyss/background/roleStarBg4.png"
        elif value == 5:
            return "./../abyss/background/roleStarBg5.png"
        else:
            raise ValueError("错误的数据")

    @staticmethod
    async def _get_data_from_user(user: User):
        try:
            logger.debug("尝试获取已绑定的原神账号")
            client = await get_genshin_client(user.id)
            logger.debug(f"获取成功, UID: {client.uid}")
            characters = await client.get_genshin_characters(client.uid)
            return [character.name for character in characters]
        except (UserNotFoundError, CookiesNotFoundError):
            logger.info(f"未查询到用户({user.full_name} {user.id}) 所绑定的账号信息")
            return []

    @handler(CommandHandler, command="abyss_team", block=False)
    @handler(MessageHandler, filters=filters.Regex("^深渊推荐配队(.*)"), block=False)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, _: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 查深渊推荐配队命令请求")
        await message.reply_chat_action(ChatAction.TYPING)
        team_data = await self.team_data.get_data()
        # 尝试获取用户已绑定的原神账号信息
        user_data = await self._get_data_from_user(user)
        team_data.sort(user_data)
        random_team = team_data.randomTeam()
        abyss_team_data = {
            "up": [],
            "down": []
        }
        for i in random_team.up.formation:
            temp = {
                "icon": (await self.assets_service.avatar(roleToId(i.name)).icon()).as_uri(),
                "name": i.name,
                "background": self._get_role_star_bg(i.star),
                "hava": (i.name in user_data) if user_data else True,
            }
            abyss_team_data["up"].append(temp)
        for i in random_team.down.formation:
            temp = {
                "icon": (await self.assets_service.avatar(roleToId(i.name)).icon()).as_uri(),
                "name": i.name,
                "background": self._get_role_star_bg(i.star),
                "hava": (i.name in user_data) if user_data else True,
            }
            abyss_team_data["down"].append(temp)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        png_data = await self.template_service.render('genshin/abyss_team', "abyss_team.html", abyss_team_data,
                                                      {"width": 865, "height": 504}, full_page=False)
        await message.reply_photo(png_data, filename=f"abyss_team_{user.id}.png",
                                  allow_sending_without_reply=True)
