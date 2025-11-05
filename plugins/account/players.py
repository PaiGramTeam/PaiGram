import html
from http.cookies import SimpleCookie
from typing import Tuple, TYPE_CHECKING

from simnet import Region, GenshinClient
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import filters
from core.config import config
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.players.services import PlayerInfoService
from gram_core.services.cookies.models import CookiesStatusEnum
from gram_core.services.devices import DevicesService
from modules.apihelper.models.genshin.cookies import CookiesModel
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


__all__ = ("PlayersManagesPlugin",)


class PlayersManagesPlugin(Plugin):
    def __init__(
        self,
        players: PlayersService,
        cookies: CookiesService,
        player_info_service: PlayerInfoService,
        devices_service: DevicesService,
    ):
        self.cookies_service = cookies
        self.players_service = players
        self.player_info_service = player_info_service
        self.devices_service = devices_service

    @staticmethod
    def players_manager_callback(callback_query_data: str) -> Tuple[str, int, int]:
        _data = callback_query_data.split("|")
        _handle = _data[-3]
        _user_id = int(_data[-2])
        _player_id = int(_data[-1])
        logger.debug(
            "players_manager_callback函数返回 handle[%s] user_id[%s] player_id[%s]", _handle, _user_id, _player_id
        )
        return _handle, _user_id, _player_id

    @handler.command(command="player", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="players", filters=filters.ChatType.PRIVATE, block=False)
    @handler.callback_query(r"^players_manager\|list", block=False)
    async def command_start(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = update.effective_user
        message = update.effective_message
        players = await self.players_service.get_all_by_user_id(user.id)
        if len(players) == 0:
            if callback_query:
                await callback_query.edit_message_text(config.notice.user_not_found)
            else:
                await message.reply_text(config.notice.user_not_found)
            return
        buttons = []
        for player in players:
            player_info = await self.player_info_service.get(player)
            text = f"{player.player_id} {player_info.nickname}"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text,
                        callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                    )
                ]
            )
        if callback_query:
            await callback_query.edit_message_text(
                "从下面的列表中选择一个玩家", reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await message.reply_text("从下面的列表中选择一个玩家", reply_markup=InlineKeyboardMarkup(buttons))

    @handler.callback_query(r"^players_manager\|get\|", block=False)
    async def get_player(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        _, user_id, player_id = self.players_manager_callback(callback_query.data)
        if user.id != user_id:
            if callback_query.message:
                await callback_query.message.delete()
            return

        player = await self.players_service.get(user.id, player_id=player_id)
        if player is None:
            await callback_query.edit_message_text(f"账号 {player_id} 未找到")
            return

        player_info = await self.player_info_service.get(player)
        if player_info is None:
            await callback_query.edit_message_text(f"账号 {player_id} 信息未找到")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    "设置为主账号",
                    callback_data=f"players_manager|main|{user.id}|{player.player_id}",
                ),
                InlineKeyboardButton(
                    "删除账号",
                    callback_data=f"players_manager|del|{user.id}|{player.player_id}",
                ),
                InlineKeyboardButton(
                    "更新账号信息",
                    callback_data=f"players_manager|update|{user.id}|{player.player_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "« 返回玩家列表",
                    callback_data="players_manager|list",
                )
            ],
        ]

        if player.account_id is not None:
            cookies = await self.cookies_service.get(player.user_id, player.account_id, player.region)
            if cookies is not None:
                temp_buttons = [
                    InlineKeyboardButton(
                        "导出 Cookies",
                        callback_data=f"players_manager|export_cookies|{user.id}|{player.player_id}",
                    ),
                    InlineKeyboardButton(
                        "刷新 Cookies",
                        callback_data=f"players_manager|refresh_cookies|{user.id}|{player.player_id}",
                    ),
                ]

                buttons.insert(-1, temp_buttons)

        await callback_query.edit_message_text(
            f"这里是 {player.player_id} {player_info.nickname}\n你想用这个账号做什么？",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    @handler.callback_query(r"^players_manager\|update\|", block=False)
    async def update_user(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        _, user_id, player_id = self.players_manager_callback(callback_query.data)
        if user.id != user_id:
            if callback_query.message:
                await callback_query.message.delete()
            return

        player = await self.players_service.get(user.id, player_id=player_id)
        if player is None:
            await callback_query.edit_message_text(f"账号 {player_id} 未找到")
            return

        status = await self.player_info_service.update_from_enka(player)

        buttons = [
            [
                InlineKeyboardButton(
                    "« 返回",
                    callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                )
            ],
        ]

        if status:
            await callback_query.edit_message_text(
                f"更新玩家信息 {player.player_id} 成功", reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await callback_query.edit_message_text(
                f"更新玩家信息 {player.player_id} 更新失败 请稍后重试", reply_markup=InlineKeyboardMarkup(buttons)
            )

    @handler.callback_query(r"^players_manager\|refresh_cookies\|", block=False)
    async def refresh_cookies(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        _, user_id, player_id = self.players_manager_callback(callback_query.data)
        if user.id != user_id:
            if callback_query.message:
                await callback_query.message.delete()
            return

        player = await self.players_service.get(user.id, player_id=player_id)
        if player is None:
            await callback_query.edit_message_text(f"账号 {player_id} 未找到")
            return

        player_info = await self.player_info_service.get(player)
        if player_info is None:
            await callback_query.edit_message_text(f"账号 {player_id} 信息未找到")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    "« 返回",
                    callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                )
            ],
        ]

        cookies_data = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookies_data is None:
            await callback_query.edit_message_text(
                f"玩家 {player.player_id} {player_info.nickname} cookies 未找到",
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        cookies = CookiesModel(**cookies_data.data)

        if cookies.stoken is not None:
            try:
                region = Region.CHINESE if player.region.value == 1 else Region.OVERSEAS
                async with GenshinClient(cookies=cookies.to_dict(), region=region) as client:
                    old_cookies = cookies.to_dict()
                    new_cookies = await client.get_all_token_by_stoken()
                    logger.success("用户 %s 刷新所有 token 成功", user_id)
                    new_cookies_dict = new_cookies.to_dict()
                    # 保留云游戏相关字段
                    cg_cookies = {k: v for k, v in old_cookies.items() if k.startswith("cg_")}
                    new_cookies_dict.update(cg_cookies)
                    cookies = CookiesModel(**new_cookies_dict)
            except Exception as exc:  # pylint: disable=W0703
                logger.error("刷新 cookie_token 失败 [%s]", (str(exc)))
                await callback_query.edit_message_text(
                    f"玩家 {player.player_id} {player_info.nickname} cookies 刷新失败 可能 stoken 已经过期",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return
            cookies_data.data = cookies.to_dict()
            cookies_data.status = CookiesStatusEnum.STATUS_SUCCESS
            await self.cookies_service.update(cookies_data)
            await callback_query.edit_message_text(
                f"玩家 {player.player_id} {player_info.nickname} cookies 刷新成功",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        else:
            await callback_query.edit_message_text(
                f"玩家 {player.player_id} {player_info.nickname} stoken 未找到",
                reply_markup=InlineKeyboardMarkup(buttons),
            )

    @handler.callback_query(r"^players_manager\|export_cookies\|", block=False)
    async def export_cookies(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        message = update.effective_message
        user = callback_query.from_user

        _, user_id, player_id = self.players_manager_callback(callback_query.data)
        if user.id != user_id:
            if callback_query.message:
                await callback_query.message.delete()
            return

        player = await self.players_service.get(user.id, player_id=player_id)
        if player is None:
            await callback_query.edit_message_text(f"账号 {player_id} 未找到")
            return

        player_info = await self.player_info_service.get(player)
        if player_info is None:
            await callback_query.edit_message_text(f"账号 {player_id} 信息未找到")
            return

        buttons = [
            [
                InlineKeyboardButton(
                    "« 返回",
                    callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                )
            ],
        ]

        cookies_data = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookies_data is None:
            await callback_query.edit_message_text(
                f"玩家 {player.player_id} {player_info.nickname} cookies 未找到",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return
        device = await self.devices_service.get(player.account_id)

        cookies = SimpleCookie()
        for key, value in cookies_data.data.items():
            cookies[key] = value
        if device is not None:
            cookies["x-rpc-device_id"] = device.device_id
            cookies["x-rpc-device_fp"] = device.device_fp

        cookie_str = cookies.output(header="", sep=";")

        await message.reply_html(
            f"<pre>{html.escape(cookie_str)}</pre>",
        )
        await message.reply_text(
            f"玩家 {player.player_id} {player_info.nickname} cookies 导出成功",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        await message.delete()

    @handler.callback_query(r"^players_manager\|main\|", block=False)
    async def set_main(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        _, user_id, player_id = self.players_manager_callback(callback_query.data)
        if user.id != user_id:
            if callback_query.message:
                await callback_query.message.delete()
            return

        player = await self.players_service.get(user.id, player_id=player_id)
        if player is None:
            await callback_query.edit_message_text(f"账号 {player_id} 未找到")
            return

        player_info = await self.player_info_service.get(player)
        if player_info is None:
            await callback_query.edit_message_text(f"账号 {player_id} 信息未找到")
            return

        await self.players_service.set_player_to_main(user_id, player_id)

        buttons = [
            [
                InlineKeyboardButton(
                    "« 返回",
                    callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                )
            ],
        ]

        await callback_query.edit_message_text(
            f"成功设置 {player.player_id} {player_info.nickname} 为主账号", reply_markup=InlineKeyboardMarkup(buttons)
        )

    @handler.callback_query(r"^players_manager\|del\|", block=False)
    async def delete(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        callback_query = update.callback_query
        user = callback_query.from_user

        _handle, user_id, player_id = self.players_manager_callback(callback_query.data)
        if user.id != user_id:
            if callback_query.message:
                await callback_query.message.delete()
            return

        player = await self.players_service.get(user.id, player_id=player_id)
        if player is None:
            await callback_query.edit_message_text(f"账号 {player_id} 未找到")
            return

        player_info = await self.player_info_service.get_form_sql(player)
        if player_info is None:
            await callback_query.edit_message_text(f"账号 {player_id} 信息未找到")
            return

        if _handle == "true":
            buttons = [
                [
                    InlineKeyboardButton(
                        "« 返回玩家列表",
                        callback_data="players_manager|list",
                    )
                ],
            ]
            await self.players_service.delete(player)
            cookies = await self.cookies_service.get(player.user_id, player.account_id, player.region)
            if cookies:
                players = await self.players_service.get_all_by_account_id(cookies.account_id, cookies.region)
                if len(players) == 0:
                    await self.cookies_service.delete(cookies)
            player_info = await self.player_info_service.get_form_sql(player)
            if player_info is not None:
                await self.player_info_service.delete(player_info)
            await callback_query.edit_message_text(
                f"成功删除 {player.player_id} ", reply_markup=InlineKeyboardMarkup(buttons)
            )
        elif _handle == "del":
            buttons = [
                [
                    InlineKeyboardButton(
                        "是的我非常确定",
                        callback_data=f"players_manager|del|true|{user.id}|{player.player_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "取消操作",
                        callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                    )
                ],
            ]
            await callback_query.edit_message_text(
                "请问你真的要从Bot中删除改账号吗？", reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            if callback_query.message:
                await callback_query.message.delete()
