import asyncio
from typing import cast, Dict, Awaitable, List
from uuid import uuid4

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update, InlineQuery
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, InlineQueryHandler

from core.base.assets import AssetsService, AssetsCouldNotFound
from core.plugin import handler, Plugin
from core.wiki import WikiService
from utils.decorators.error import error_callable
from utils.log import logger


class Inline(Plugin):
    """Inline模块"""

    def __init__(
        self,
        wiki_service: WikiService = None,
        assets_service: AssetsService = None,
    ):
        self.assets_service = assets_service
        self.wiki_service = wiki_service
        self.weapons_list: List[Dict[str, str]] = []
        self.characters_list: List[Dict[str, str]] = []
        self.refresh_task: List[Awaitable] = []

    async def __async_init__(self):
        # todo: 整合进 wiki 或者单独模块 从Redis中读取
        async def task_weapons():
            logger.info("Inline 模块正在获取武器列表")
            weapons_list = await self.wiki_service.get_weapons_name_list()
            for weapons_name in weapons_list:
                try:
                    icon = await self.assets_service.weapon(weapons_name).get_link("icon")
                except AssetsCouldNotFound:
                    continue
                data = {"name": weapons_name, "icon": icon}
                self.weapons_list.append(data)
            logger.success("Inline 模块获取武器列表成功")

        async def task_characters():
            logger.info("Inline 模块正在获取角色列表")
            characters_list = await self.wiki_service.get_characters_name_list()
            for character_name in characters_list:
                try:
                    icon = await self.assets_service.avatar(character_name).get_link("icon")
                except AssetsCouldNotFound:
                    continue
                data = {"name": character_name, "icon": icon}
                self.characters_list.append(data)
            logger.success("Inline 模块获取角色列表成功")

        self.refresh_task.append(asyncio.create_task(task_weapons()))
        self.refresh_task.append(asyncio.create_task(task_characters()))

    @handler(InlineQueryHandler, block=False)
    @error_callable
    async def inline_query(self, update: Update, _: CallbackContext) -> None:
        user = update.effective_user
        ilq = cast(InlineQuery, update.inline_query)
        query = ilq.query
        logger.info("用户 %s[%s] inline_query 查询\nquery[%s]", user.full_name, user.id, query)
        switch_pm_text = "需要帮助嘛？"
        results_list = []
        args = query.split(" ")
        if args[0] == "":
            pass
        else:
            if "查看武器列表并查询" == args[0]:
                for weapon in self.weapons_list:
                    name = weapon["name"]
                    icon = weapon["icon"]
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=name,
                            description=f"查看武器列表并查询 {name}",
                            thumb_url=icon,
                            input_message_content=InputTextMessageContent(
                                f"武器查询{name}", parse_mode=ParseMode.MARKDOWN_V2
                            ),
                        )
                    )
            elif "查看角色攻略列表并查询" == args[0]:
                for character in self.characters_list:
                    name = character["name"]
                    icon = character["icon"]
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=name,
                            description=f"查看角色攻略列表并查询 {name}",
                            thumb_url=icon,
                            input_message_content=InputTextMessageContent(
                                f"角色攻略查询{name}", parse_mode=ParseMode.MARKDOWN_V2
                            ),
                        )
                    )
            elif "查看角色培养素材列表并查询" == args[0]:
                characters_list = await self.wiki_service.get_characters_name_list()
                for role_name in characters_list:
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=role_name,
                            description=f"查看角色培养素材列表并查询 {role_name}",
                            input_message_content=InputTextMessageContent(
                                f"角色培养素材查询{role_name}", parse_mode=ParseMode.MARKDOWN_V2
                            ),
                        )
                    )

        if not results_list:
            results_list.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="好像找不到问题呢",
                    description="这个问题我也不知道，因为我就是个应急食品。",
                    input_message_content=InputTextMessageContent("这个问题我也不知道，因为我就是个应急食品。"),
                )
            )
        try:
            await ilq.answer(
                results=results_list,
                switch_pm_text=switch_pm_text,
                switch_pm_parameter="inline_message",
                cache_time=0,
                auto_pagination=True,
            )
        except BadRequest as exc:
            if "Query is too old" in exc.message:  # 过时请求全部忽略
                logger.warning("用户 %s[%s] inline_query 请求过时", user.full_name, user.id)
                return
            if "can't parse entities" not in exc.message:
                raise exc
            logger.warning("inline_query发生BadRequest错误", exc_info=exc)
            await ilq.answer(
                results=[],
                switch_pm_text="糟糕，发生错误了。",
                switch_pm_parameter="inline_message",
            )
