import asyncio
from typing import Awaitable, Dict, List, cast
from uuid import uuid4

from telegram import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
    Update,
    InlineQueryResultsButton,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext

from core.dependence.assets import AssetsCouldNotFound, AssetsService
from core.plugin import Plugin, handler
from core.services.search.services import SearchServices
from core.services.wiki.services import WikiService
from utils.log import logger


class Inline(Plugin):
    """Inline模块"""

    def __init__(
        self,
        wiki_service: WikiService,
        assets_service: AssetsService,
        search_service: SearchServices,
    ):
        self.assets_service = assets_service
        self.wiki_service = wiki_service
        self.weapons_list: List[Dict[str, str]] = []
        self.characters_list: List[Dict[str, str]] = []
        self.refresh_task: List[Awaitable] = []
        self.search_service = search_service

    async def initialize(self):
        # todo: 整合进 wiki 或者单独模块 从Redis中读取
        async def task_weapons():
            logger.info("Inline 模块正在获取武器列表")
            weapons_list = await self.wiki_service.get_weapons_name_list()
            for weapons_name in weapons_list:
                try:
                    icon = await self.assets_service.weapon(weapons_name).get_link("icon")
                except AssetsCouldNotFound:
                    continue
                except Exception as exc:
                    logger.error("获取武器信息失败 %s", str(exc))
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
                except Exception as exc:
                    logger.error("获取角色信息失败 %s", str(exc))
                    continue
                data = {"name": character_name, "icon": icon}
                self.characters_list.append(data)
            logger.success("Inline 模块获取角色列表成功")

        self.refresh_task.append(asyncio.create_task(task_weapons()))
        self.refresh_task.append(asyncio.create_task(task_characters()))

    @handler.inline_query(block=False)
    async def inline_query(self, update: Update, _: CallbackContext) -> None:
        user = update.effective_user
        ilq = cast(InlineQuery, update.inline_query)
        query = ilq.query
        logger.info("用户 %s[%s] inline_query 查询\nquery[%s]", user.full_name, user.id, query)
        switch_pm_text = "需要帮助嘛？"
        results_list = []
        args = query.split(" ")
        if args[0] == "":
            results_list.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="武器图鉴查询",
                    description="输入武器名称即可查询武器图鉴",
                    input_message_content=InputTextMessageContent("武器图鉴查询"),
                )
            )
            results_list.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="角色攻略查询",
                    description="输入角色名即可查询角色攻略",
                    input_message_content=InputTextMessageContent("角色攻略查询"),
                )
            )
        elif args[0] == "cookies_export":
            return
        else:
            if args[0] == "查看武器列表并查询":
                for weapon in self.weapons_list:
                    name = weapon["name"]
                    icon = weapon["icon"]
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=name,
                            description=f"查看武器列表并查询 {name}",
                            thumbnail_url=icon,
                            input_message_content=InputTextMessageContent(
                                f"武器查询{name}", parse_mode=ParseMode.MARKDOWN_V2
                            ),
                        )
                    )
            elif args[0] == "查看角色攻略列表并查询":
                for character in self.characters_list:
                    name = character["name"]
                    icon = character["icon"]
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=name,
                            description=f"查看角色攻略列表并查询 {name}",
                            thumbnail_url=icon,
                            input_message_content=InputTextMessageContent(
                                f"角色攻略查询{name}", parse_mode=ParseMode.MARKDOWN_V2
                            ),
                        )
                    )
            elif args[0] == "查看角色培养素材列表并查询":
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
            else:
                simple_search_results = await self.search_service.search(args[0])
                if simple_search_results:
                    results_list.append(
                        InlineQueryResultArticle(
                            id=str(uuid4()),
                            title=f"当前查询内容为 {args[0]}",
                            description="如果无查看图片描述 这是正常的 客户端问题",
                            thumbnail_url="https://www.miyoushe.com/_nuxt/img/game-ys.dfc535b.jpg",
                            input_message_content=InputTextMessageContent(
                                f"当前查询内容为 {args[0]}\n如果无查看图片描述 这是正常的 客户端问题"
                            ),
                        )
                    )
                    for simple_search_result in simple_search_results:
                        if simple_search_result.photo_file_id:
                            description = simple_search_result.description
                            if len(description) >= 10:
                                description = description[:10]
                            results_list.append(
                                InlineQueryResultCachedPhoto(
                                    id=str(uuid4()),
                                    title=simple_search_result.title,
                                    photo_file_id=simple_search_result.photo_file_id,
                                    description=description,
                                    caption=simple_search_result.caption,
                                    parse_mode=simple_search_result.parse_mode,
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
                cache_time=0,
                auto_pagination=True,
                button=InlineQueryResultsButton(
                    text=switch_pm_text,
                    start_parameter="inline_message",
                ),
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
                button=InlineQueryResultsButton(
                    text="糟糕，发生错误了。",
                    start_parameter="inline_message",
                ),
            )
