"""Recommend teams for Spiral Abyss"""

import re

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters

from core.dependence.assets import AssetsService
from core.plugin import Plugin, handler
from core.services.template.services import TemplateService
from metadata.genshin import AVATAR_DATA
from metadata.shortname import idToName
from modules.apihelper.client.components.abyss import AbyssTeam as AbyssTeamClient
from plugins.tools.genshin import GenshinHelper
from utils.log import logger


class AbyssTeamPlugin(Plugin):
    """Recommend teams for Spiral Abyss"""

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
    @handler.message(filters.Regex(r"^深渊配队"), block=False)
    async def command_start(self, update: Update, _: CallbackContext) -> None:  # skipcq: PY-R1000 #
        user_id = await self.get_real_user_id(update)
        message = update.effective_message

        if "help" in message.text or "帮助" in message.text:
            await message.reply_text(
                "<b>深渊配队推荐</b>功能使用帮助（中括号表示可选参数）\n\n"
                "指令格式：\n<code>/abyss_team [n=配队数]</code>\n（<code>pre</code>表示上期）\n\n"
                "文本格式：\n<code>深渊配队 [n=配队数]</code> \n\n"
                "如：\n"
                "<code>/abyss_team</code>\n<code>/abyss_team n=5</code>\n"
                "<code>深渊配队</code>\n",
                parse_mode=ParseMode.HTML,
            )
            self.log_user(update, logger.info, "查询[bold]深渊配队推荐[/bold]帮助", extra={"markup": True})
            return

        self.log_user(update, logger.info, "[bold]深渊配队推荐[/bold]请求", extra={"markup": True})

        client = await self.helper.get_genshin_client(user_id)

        await message.reply_chat_action(ChatAction.TYPING)
        team_data = await self.team_data.get_data()

        # Set of uids
        characters = {c.id for c in await client.get_genshin_characters(client.player_id)}

        teams = {
            "Up": [],
            "Down": [],
        }

        # All of the effective and available teams
        for lane in ["Up", "Down"]:
            for a_team in team_data[12 - 9][lane]:
                t_characters = [int(s) for s in re.findall(r"\d+", a_team["Item"])]
                t_rate = a_team["Rate"]

                # Check availability
                if not all(c in characters for c in t_characters):
                    continue

                teams[lane].append(
                    {
                        "Characters": t_characters,
                        "Rate": t_rate,
                    }
                )

        # If a number is specified, use it as the number of expected teams.
        match = re.search(r"(?<=n=)\d+", message.text)
        n_team = int(match.group()) if match is not None else 4

        if "fast" in message.text:
            # TODO: Give it a faster method?
            # Maybe we can allow characters exist on both side.
            return

        # Otherwise, we'd find a team in a complexity
        # O(len(teams[up]) * len(teams[down]))

        abyss_teams_data = {"uid": client.player_id, "teams": []}

        async def _get_render_data(id_list):
            return [
                {
                    "icon": (await self.assets_service.avatar(cid).icon()).as_uri(),
                    "name": idToName(cid),
                    "star": AVATAR_DATA[str(cid)]["rank"] if cid not in {10000005, 10000007} else 5,
                    "hava": True,
                }
                for cid in id_list
            ]

        for u in teams["Up"]:
            for d in teams["Down"]:
                if not all(c not in d["Characters"] for c in u["Characters"]):
                    continue
                team = {
                    "Up": await _get_render_data(u["Characters"]),
                    "UpRate": u["Rate"],
                    "Down": await _get_render_data(d["Characters"]),
                    "DownRate": d["Rate"],
                }
                abyss_teams_data["teams"].append(team)
        abyss_teams_data["teams"].sort(key=lambda t: t["UpRate"] * t["DownRate"], reverse=True)
        abyss_teams_data["teams"] = abyss_teams_data["teams"][0 : min(n_team, len(abyss_teams_data["teams"]))]

        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        render_result = await self.template_service.render(
            "genshin/abyss_team/abyss_team.jinja2",
            abyss_teams_data,
            {"width": 785, "height": 800},
            full_page=True,
            query_selector=".bg-contain",
        )
        await render_result.reply_photo(message, filename=f"abyss_team_{user_id}.png", allow_sending_without_reply=True)
