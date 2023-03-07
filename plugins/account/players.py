import asyncio
from typing import Tuple

import genshin
from aiohttp import ClientConnectorError
from enkanetwork import EnkaNetworkAPI, EnkaPlayerNotFound, HTTPException, VaildateUIDError
from genshin import GenshinException
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import filters, ContextTypes

from core.config import config
from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from core.services.players import PlayersService
from core.services.players.models import RegionEnum
from utils.enkanetwork import RedisCache
from utils.log import logger

__all__ = ("PlayersManagesPlugin",)

from utils.patch.aiohttp import AioHttpTimeoutException


class PlayersManagesPlugin(Plugin):
    def __init__(self, players: PlayersService, cookies: CookiesService, redis: RedisDB):
        self.cookies_service = cookies
        self.players_service = players
        self.enka_client = EnkaNetworkAPI(lang="chs", user_agent=config.enka_network_api_agent)
        self.enka_client.set_cache(RedisCache(redis.client, key="plugin:players_manages:enka_network", ttl=60 * 60 * 3))

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
    async def command_start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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
        await message.reply_text("从下面的列表中选择一个玩家", reply_markup=InlineKeyboardMarkup(buttons))

    @handler.callback_query(r"^players_manager\|get\|", block=False)
    async def get_player(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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
                InlineKeyboardButton(
                    "更新在数据库数据",
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

        await callback_query.edit_message_text(
            f"这里是 {player.player_id} {player.nickname}\n你想用这个账号做什么？", reply_markup=InlineKeyboardMarkup(buttons)
        )

    @handler.callback_query(r"^players_manager\|update\|", block=False)
    async def update_user(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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

        await callback_query.edit_message_text("正在从服务器更新")

        cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookie_model:
            uid = player.player_id
            region = player.region
            if region == RegionEnum.HYPERION:  # 国服
                game_region = genshin.types.Region.CHINESE
            elif region == RegionEnum.HOYOLAB:  # 国际服
                game_region = genshin.types.Region.OVERSEAS
            else:
                raise TypeError("Region is not None")
            client = genshin.Client(
                cookie_model.data, lang="zh-cn", game=genshin.types.Game.GENSHIN, region=game_region, uid=uid
            )
            try:
                genshin_accounts = await client.genshin_accounts()
                for genshin_account in genshin_accounts:
                    if genshin_account.uid == player.player_id:
                        player.nickname = genshin_account.nickname
                        break
                else:
                    await callback_query.edit_message_text("奇怪的错误")
                    return
            except GenshinException:
                logger.warning("服务器请求失败")
                return

        await self.players_service.update(player)

        await asyncio.sleep(1)

        await callback_query.edit_message_text("正在从Enka服务器更新")
        try:
            enka_network_response = await self.enka_client.fetch_user(player.player_id, info=True)
            player.name_card_id = enka_network_response.player.namecard.id
            player.signature = enka_network_response.player.signature
            if player.nickname is None:
                player.nickname = enka_network_response.player.nickname
            player.hand_image = enka_network_response.player.avatar.id
            await self.players_service.update(player)
        except (VaildateUIDError, EnkaPlayerNotFound) as exc:
            logger.warning("EnkaNetwork 请求失败: %s", str(exc))
            await callback_query.edit_message_text("EnkaNetwork 请求失败 玩家信息有误")
        except (AioHttpTimeoutException, ClientConnectorError, HTTPException) as exc:
            await callback_query.edit_message_text("EnkaNetwork 请求超时")
            logger.warning("EnkaNetwork 请求超时: %s", str(exc))
        except Exception as exc:
            await callback_query.edit_message_text("EnkaNetwork 请求失败")
            logger.error("EnkaNetwork 请求失败: %s", exc_info=exc)

        await asyncio.sleep(1)

        await callback_query.edit_message_text("更新成功")

        buttons = [
            [
                InlineKeyboardButton(
                    "« 返回",
                    callback_data=f"players_manager|get|{user.id}|{player.player_id}",
                )
            ],
        ]

        await callback_query.edit_message_text(
            f"更新玩家信息 {player.player_id} {player.nickname} 成功", reply_markup=InlineKeyboardMarkup(buttons)
        )

    @handler.callback_query(r"^players_manager\|main\|", block=False)
    async def set_main(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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
    async def delete(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
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
                        callback_data="players_manager|list",
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
