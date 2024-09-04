import random
from pathlib import Path
from typing import Optional, TYPE_CHECKING, List
from telegram.constants import ChatAction
from telegram.ext import filters

from core.config import config
from core.plugin import Plugin, handler
from core.services.cookies.error import TooManyRequestPublicCookies
from core.services.template.models import RenderResult
from core.services.template.services import TemplateService
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from plugins.tools.genshin import GenshinHelper
from utils.const import RESOURCE_DIR
from utils.error import UrlResourcesNotFoundError
from utils.log import logger
from utils.uid import mask_number

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes
    from simnet.models.genshin.chronicle.stats import GenshinUserStats
    from simnet import GenshinClient

__all__ = ("PlayerStatsPlugins",)


class PlayerStatsPlugins(Plugin):
    """玩家统计查询"""

    def __init__(self, template: TemplateService, helper: GenshinHelper):
        self.template_service = template
        self.helper = helper

    @handler.command("stats", player=True, block=False)
    @handler.message(filters.Regex("^玩家统计查询(.*)"), player=True, block=False)
    async def command_start(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "查询游戏用户命令请求")
        try:
            async with self.helper.genshin_or_public(user_id, uid=uid, offset=offset) as client:
                if not client.public:
                    await client.get_record_cards()
                render_result = await self.render(client, client.player_id)
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多 请稍后重试")
            return
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

        user_info = await client.get_genshin_user(uid)

        # 因为需要替换线上图片地址为本地地址，先克隆数据，避免修改原数据
        user_info = user_info.copy(deep=True)

        data = {
            "uid": mask_number(uid),
            "info": user_info.info,
            "stats": user_info.stats,
            "explorations": user_info.explorations,
            "skip_explor": [10],
            "teapot": user_info.teapot,
            "stats_labels": [
                ("活跃天数", "days_active"),
                ("成就达成数", "achievements"),
                ("获取角色数", "characters"),
                ("满好感角色数", "full_fetter_avatar_num"),
                ("深境螺旋", "spiral_abyss"),
                ("解锁传送点", "unlocked_waypoints"),
                ("解锁秘境", "unlocked_domains"),
                ("奇馈宝箱数", "remarkable_chests"),
                ("华丽宝箱数", "luxurious_chests"),
                ("珍贵宝箱数", "precious_chests"),
                ("精致宝箱数", "exquisite_chests"),
                ("普通宝箱数", "common_chests"),
                ("风神瞳", "anemoculi"),
                ("岩神瞳", "geoculi"),
                ("雷神瞳", "electroculi"),
                ("草神瞳", "dendroculi"),
                ("水神瞳", "hydroculi"),
                ("火神瞳", "pyroculi"),
            ],
            "style": random.choice(["mondstadt", "liyue"]),  # nosec
        }

        await self.cache_images(user_info)

        return await self.template_service.render(
            "genshin/stats/stats.jinja2",
            data,
            {"width": 650, "height": 800},
            full_page=True,
        )

    async def _download_resource(self, url: str) -> str:
        try:
            return await self.download_resource(url)
        except Exception:
            path = Path(url)
            file_path = RESOURCE_DIR / "img" / "city" / path.name
            if file_path.exists():
                return file_path.as_uri()
            logger.warning("缓存地区图片资源失败 %s", url)

    async def cache_images(self, data: "GenshinUserStats") -> None:
        """缓存所有图片到本地"""
        # TODO: 并发下载所有资源

        # 探索地区
        for item in data.explorations:
            item.__config__.allow_mutation = True
            item.icon = await self._download_resource(item.icon)
            item.cover = await self._download_resource(item.cover)

    async def stats_use_by_inline(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        callback_query = update.callback_query
        user = update.effective_user
        user_id = user.id
        uid = IInlineUseData.get_uid_from_context(context)

        self.log_user(update, logger.info, "查询游戏用户命令请求")
        notice = None
        try:
            async with self.helper.genshin_or_public(user_id, uid=uid) as client:
                if not client.public:
                    await client.get_record_cards()
                render_result = await self.render(client, client.player_id)
        except TooManyRequestPublicCookies:
            notice = "用户查询次数过多 请稍后重试"
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
                text="玩家统计",
                hash="stats",
                callback=self.stats_use_by_inline,
                player=True,
            ),
        ]
