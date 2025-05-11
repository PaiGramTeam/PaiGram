import asyncio
from typing import Awaitable, Dict, List, cast, Tuple
from uuid import uuid4

from telegram import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultCachedPhoto,
    InputTextMessageContent,
    Update,
    InlineQueryResultsButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackContext, ContextTypes

from core.dependence.assets.impl.genshin import AssetsCouldNotFound, AssetsService
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.search.services import SearchServices
from gram_core.config import config
from gram_core.plugin.methods.inline_use_data import IInlineUseData
from utils.log import logger


class Inline(Plugin):
    """Inline模块"""

    def __init__(
        self,
        assets_service: AssetsService,
        search_service: SearchServices,
        cookies_service: CookiesService,
        players_service: PlayersService,
    ):
        self.assets_service = assets_service
        self.weapons_list: List[Dict[str, str]] = []
        self.characters_list: List[Dict[str, str]] = []
        self.refresh_task: List[Awaitable] = []
        self.search_service = search_service
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.inline_use_data: List[IInlineUseData] = []
        self.inline_use_data_map: Dict[str, IInlineUseData] = {}
        self.img_url = "https://i.dawnlab.me/b1bdf9cc3061d254f038e557557694bc.jpg"

    async def initialize(self):
        # todo: 整合进 wiki 或者单独模块 从Redis中读取
        async def task_weapons():
            logger.info("Inline 模块正在获取武器列表")
            for weapons_name in self.assets_service.weapon.get_name_list():
                try:
                    icon = self.assets_service.weapon.get_by_id(weapons_name).icon.url
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
            for character_name in self.assets_service.avatar.get_name_list():
                try:
                    icon = self.assets_service.avatar.get_by_id(character_name).icon.url
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

    async def init_inline_use_data(self):
        if self.inline_use_data:
            return
        for _, instance in self.application.managers.plugins_map.items():
            if _data := await instance.get_inline_use_data():
                self.inline_use_data.extend(_data)
        for data in self.inline_use_data:
            self.inline_use_data_map[data.hash] = data

    async def user_base_data(self, user_id: int, player_id: int, offset: int) -> Tuple[int, bool, bool]:
        uid, has_cookie, has_player = 0, False, False
        player = await self.players_service.get_player(user_id, None, player_id, offset)
        if player is not None:
            uid = player.player_id
            has_player = True
            if player.account_id is not None:
                cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
                if cookie_model is not None:
                    has_cookie = True
        return uid, has_cookie, has_player

    def get_inline_use_button_data(self, user_id: int, uid: int, cookie: bool, player: bool) -> InlineKeyboardMarkup:
        button_data = []
        start = f"use_inline_func|{user_id}|{uid}"
        for data in self.inline_use_data:
            if data.is_show(cookie, player):
                button_data.append(
                    InlineKeyboardButton(text=data.text, callback_data=data.get_button_callback_data(start))
                )
        # 每三个一行
        button_data = [button_data[i : i + 3] for i in range(0, len(button_data), 3)]
        return InlineKeyboardMarkup(button_data)

    @handler.callback_query(pattern=r"^use_inline_func\|", block=False)
    async def use_by_inline_query_callback(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user = update.effective_user
        callback_query = update.callback_query

        async def get_inline_query_callback(callback_query_data: str) -> Tuple[int, int, str]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _uid = int(_data[2])
            _hash = _data[3]
            logger.debug("callback_query_data函数返回 user_id[%s] uid[%s] hash[%s]", _user_id, _uid, _hash)
            return _user_id, _uid, _hash

        user_id, uid, hash_str = await get_inline_query_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        callback = self.inline_use_data_map.get(hash_str)
        if callback is None:
            await callback_query.answer(text="数据不存在，请重新生成按钮", show_alert=True)
            return
        IInlineUseData.set_uid_to_context(context, uid)
        await callback.callback(update, context)

    @handler.inline_query(pattern="^功能", block=False)
    async def use_by_inline_query(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        if not config.channels_helper:
            logger.warning("未设置 helper 频道")
            return
        await self.init_inline_use_data()
        user = update.effective_user
        ilq = cast(InlineQuery, update.inline_query)
        query = ilq.query
        switch_pm_text = "需要帮助嘛？"
        logger.info("用户 %s[%s] inline_query 功能查询\nquery[%s]", user.full_name, user.id, query)
        user_id = user.id
        uid, offset = self.get_real_uid_or_offset(update)
        real_uid, has_cookie, has_player = await self.user_base_data(user_id, uid, offset)
        button_data = self.get_inline_use_button_data(user_id, real_uid, has_cookie, has_player)
        try:
            await ilq.answer(
                results=[
                    InlineQueryResultPhoto(
                        id=str(uuid4()),
                        photo_url=self.img_url,
                        thumbnail_url=self.img_url,
                        caption="请从下方按钮选择功能",
                        reply_markup=button_data,
                    )
                ],
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

    @handler.inline_query(block=False)
    async def z_inline_query(self, update: Update, _: CallbackContext) -> None:
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
            results_list.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="使用功能",
                    description="输入 功能 即可直接使用 BOT 功能",
                    input_message_content=InputTextMessageContent("Inline 模式下输入 功能 即可直接使用 BOT 功能"),
                )
            )
        elif args[0] == "cookies_export":
            return
        elif args[0] == "功能":
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
                for role_name in self.assets_service.avatar.get_name_list():
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
