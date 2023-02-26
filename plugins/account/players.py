from typing import Tuple

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import filters

from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from utils.log import logger

__all__ = ("PlayersManagesPlugin",)


class PlayersManagesPlugin(Plugin):
    def __init__(
        self,
        players: PlayersService,
        cookies: CookiesService,
    ):
        self.cookies_service = cookies
        self.players_service = players

    @staticmethod
    def players_manager_callback(callback_query_data: str) -> Tuple[str, int, int]:
        _data = callback_query_data.split("|")
        _handle = _data[-3]
        _user_id = int(_data[-2])
        _player_id = int(_data[-1])
        logger.debug("players_manager_callback函数返回 handle[%s] user_id[%s] player_id[%s]", _handle, _user_id, _player_id)
        return _handle, _user_id, _player_id

    @handler.command(command="player", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="players", filters=filters.ChatType.PRIVATE, block=False)
    @handler.callback_query(r"^players_manager\|list", block=False)
    async def command_start(self, update: Update) -> None:
        callback_query = update.callback_query
        user = update.effective_user
        message = update.effective_message
        players = await self.players_service.get_all_by_user_id(user.id)
        if len(players) == 0:
            if callback_query:
                await callback_query.edit_message_text("未查询到您所绑定的账号信息，请先绑定账号")
            else:
                await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号")
            return
        buttons = []
        for player in players:
            text = f"{player.player_id} {player.nickname}"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text,
                        callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                    )
                ]
            )
        if callback_query:
            await callback_query.edit_message_text("从下面的列表中选择一个玩家", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await message.reply_text("从下面的列表中选择一个玩家", reply_markup=InlineKeyboardMarkup(buttons))
        raise Exception("test")

    @handler.callback_query(r"^players_manager\|get\|", block=False)
    async def get_player(self, update: Update) -> None:
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
            ],
            [
                InlineKeyboardButton(
                    "« 返回玩家列表",
                    callback_data=f"players_manager|list",
                )
            ],
        ]

        await callback_query.edit_message_text(
            f"这里是 {player.player_id} {player.nickname}\n你想用这个账号做什么？", reply_markup=InlineKeyboardMarkup(buttons)
        )

    @handler.callback_query(r"^players_manager\|main\|", block=False)
    async def set_main(self, update: Update) -> None:
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

        main_player = await self.players_service.get(user.id, is_chosen=True)
        if main_player and player.id != main_player.id:
            main_player.is_chosen = False
            await self.players_service.update(main_player)

        player.is_chosen = True
        await self.players_service.update(player)

        buttons = [
            [
                InlineKeyboardButton(
                    "« 返回",
                    callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                )
            ],
        ]

        await callback_query.edit_message_text(
            f"成功设置 {player.player_id} {player.nickname} 为主账号", reply_markup=InlineKeyboardMarkup(buttons)
        )

    @handler.callback_query(r"^players_manager\|del\|", block=False)
    async def delete(self, update: Update) -> None:
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

        if _handle == "true":
            buttons = [
                [
                    InlineKeyboardButton(
                        "« 返回玩家列表",
                        callback_data=f"players_manager|list",
                    )
                ],
            ]
            await self.players_service.delete(player)
            cookies = await self.cookies_service.get(player.user_id, player.account_id, player.region)
            if cookies:
                await self.cookies_service.delete(cookies)
            await callback_query.edit_message_text(
                f"成功删除 {player.player_id} {player.nickname}", reply_markup=InlineKeyboardMarkup(buttons)
            )
        elif _handle == "del":
            buttons = [
                [
                    InlineKeyboardButton(
                        "不要",
                        callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                    )
                ],
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
                f"成功设置 {player.player_id} {player.nickname} 为主账号", reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            if callback_query.message:
                await callback_query.message.delete()
