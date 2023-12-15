from typing import Optional, List

from core.services.players.services import PlayerInfoService
from gram_core.plugin.methods.migrate_data import IMigrateData
from gram_core.services.cookies import CookiesService
from gram_core.services.cookies.models import CookiesDataBase as Cookies
from gram_core.services.players import PlayersService
from gram_core.services.players.models import PlayersDataBase as Player, PlayerInfoSQLModel as PlayerInfo


class AccountMigrate(IMigrateData):
    old_user_id: int
    new_user_id: int
    players_service: PlayersService
    player_info_service: PlayerInfoService
    cookies_service: CookiesService
    need_migrate_player: List[Player]
    need_migrate_player_info: List[PlayerInfo]
    need_migrate_cookies: List[Cookies]

    async def migrate_data_msg(self) -> str:
        text = []
        if self.need_migrate_player:
            text.append(f"player 数据 {len(self.need_migrate_player)} 条")
        if self.need_migrate_player_info:
            text.append(f"player_info 数据 {len(self.need_migrate_player_info)} 条")
        if self.need_migrate_cookies:
            text.append(f"cookies 数据 {len(self.need_migrate_cookies)} 条")
        return "、".join(text)

    async def migrate_data(self) -> bool:
        for player in self.need_migrate_player:
            await self.players_service.update(player)
        for player_info in self.need_migrate_player_info:
            await self.player_info_service.update(player_info)
        for cookie in self.need_migrate_cookies:
            await self.cookies_service.update(cookie)
        return True

    @staticmethod
    async def create_players(
        old_user_id: int,
        new_user_id: int,
        players_service: PlayersService,
    ) -> List[Player]:
        need_migrate = await AccountMigrate.filter_sql_data(
            Player,
            players_service.get_all_by_user_id,
            old_user_id,
            new_user_id,
            (Player.account_id, Player.player_id, Player.region),
        )
        for i in need_migrate:
            i.user_id = new_user_id
            i.is_chosen = False
        return need_migrate

    @staticmethod
    async def create_players_info(
        old_user_id: int,
        new_user_id: int,
        player_info_service: PlayerInfoService,
    ) -> List[PlayerInfo]:
        need_migrate = await AccountMigrate.filter_sql_data(
            PlayerInfo,
            player_info_service.get_all_by_user_id,
            old_user_id,
            new_user_id,
            (PlayerInfo.user_id, PlayerInfo.player_id),
        )
        for i in need_migrate:
            i.user_id = new_user_id
        return need_migrate

    @staticmethod
    async def create_cookies(
        old_user_id: int,
        new_user_id: int,
        cookies_service: CookiesService,
    ) -> List[Cookies]:
        need_migrate = await AccountMigrate.filter_sql_data(
            Cookies,
            cookies_service.get_all,
            old_user_id,
            new_user_id,
            (Cookies.user_id, Cookies.account_id, Cookies.region),
        )
        for i in need_migrate:
            i.user_id = new_user_id
        return need_migrate

    @classmethod
    async def create(
        cls,
        old_user_id: int,
        new_user_id: int,
        players_service: PlayersService,
        player_info_service: PlayerInfoService,
        cookies_service: CookiesService,
    ) -> Optional["AccountMigrate"]:
        need_migrate_player = await cls.create_players(old_user_id, new_user_id, players_service)
        need_migrate_player_info = await cls.create_players_info(old_user_id, new_user_id, player_info_service)
        need_migrate_cookies = await cls.create_cookies(old_user_id, new_user_id, cookies_service)
        if not any([need_migrate_player, need_migrate_player_info, need_migrate_cookies]):
            return None
        self = cls()
        self.old_user_id = old_user_id
        self.new_user_id = new_user_id
        self.need_migrate_player = need_migrate_player
        self.need_migrate_player_info = need_migrate_player_info
        self.need_migrate_cookies = need_migrate_cookies
        return self
