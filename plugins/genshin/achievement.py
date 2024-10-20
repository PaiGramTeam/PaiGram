from typing import Optional, TYPE_CHECKING, List
from telegram.constants import ChatAction
from telegram.ext import filters

from core.config import config
from core.plugin import Plugin, handler
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from plugins.tools.genshin import GenshinHelper
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from simnet.models.genshin.chronicle.achievement import GenshinAchievementInfo
    from simnet import GenshinClient

__all__ = ("AchievementPlugins",)


class AchievementPlugins(Plugin):
    """成就统计查询"""

    def __init__(self, template: TemplateService, helper: GenshinHelper, player_info: PlayerInfoSystem):
        self.template_service = template
        self.helper = helper
        self.player_info = player_info

    @handler.command("achievement", player=True, block=False)
    @handler.message(filters.Regex("^成就统计查询(.*)"), player=True, block=False)
    async def command_start(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "查询成就用户命令请求")
        try:
            async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
                await client.get_record_cards()
                render_result = await self.render(client, client.player_id)
        except AttributeError as exc:
            logger.error("角色数据有误")
            logger.exception(exc)
            await message.reply_text(f"角色数据有误 估计是{config.notice.bot_name}晕了")
            return
        except ValueError as exc:
            logger.warning("获取 uid 发生错误！ 错误信息为 %s", str(exc))
            await message.reply_text("输入错误")
            return
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await render_result.reply_photo(message, filename=f"{client.player_id}.png")

    async def render(self, client: "GenshinClient", uid: Optional[int] = None) -> RenderResult:
        if uid is None:
            uid = client.player_id

        achievement_info = await client.get_genshin_achievement_info(uid)
        nickname = await self.get_nickname_from_uid(uid)

        # 因为需要替换线上图片地址为本地地址，先克隆数据，避免修改原数据
        achievement_info = achievement_info.copy(deep=True)

        data = {
            "uid": mask_number(uid),
            "nickname": nickname,
            "data": achievement_info,
            "style": "liyue",
        }

        await self.cache_images(achievement_info)

        length = int(len(achievement_info.list) / 8)
        if len(achievement_info.list) % 8:
            length += 1

        return await self.template_service.render(
            "genshin/stats/achievement.jinja2",
            data,
            {"width": 2100, "height": 230 * length + 390},
            full_page=True,
        )

    async def get_nickname_from_uid(self, player_id: int) -> str:
        nickname = "Unknown"
        try:
            _, _, nickname, _ = await self.player_info.get_player_info(player_id, None, "")
        except Exception:
            logger.warning("获取玩家昵称失败 player_id[%s]", player_id)
        return nickname

    async def _download_resource(self, url: str) -> str:
        try:
            return await self.download_resource(url)
        except Exception:
            logger.warning("缓存成就图片资源失败 %s", url)

    async def cache_images(self, data: "GenshinAchievementInfo") -> None:
        """缓存所有图片到本地"""
        # TODO: 并发下载所有资源

        for item in data.list:
            item.__config__.allow_mutation = True
            if icon := await self._download_resource(item.icon):
                item.icon = icon

    async def achievement_use_by_inline(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)

        self.log_user(update, logger.info, "查询成就用户命令请求")
        notice = None
        try:
            async with self.helper.genshin(user_id, player_id=uid) as client:
                await client.get_record_cards()
                render_result = await self.render(client, client.player_id)
        except AttributeError as exc:
            logger.error("角色数据有误")
            logger.exception(exc)
            notice = f"角色数据有误 估计是{config.notice.bot_name}晕了"
        except ValueError as exc:
            logger.warning("获取 uid 发生错误！ 错误信息为 %s", str(exc))
            notice = "UID 内部错误"

        if notice:
            await callback_query.answer(notice, show_alert=True)
            return
        await render_result.edit_inline_media(callback_query)

    async def get_inline_use_data(self) -> List[Optional[IInlineUseData]]:
        return [
            IInlineUseData(
                text="成就统计",
                hash="achievement",
                callback=self.achievement_use_by_inline,
                cookie=True,
                player=True,
            ),
        ]
