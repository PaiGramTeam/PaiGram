from typing import Optional, List

from sqlalchemy.orm.exc import StaleDataError

from core.services.players.services import PlayerInfoService
from gram_core.plugin.methods.migrate_data import IMigrateData, MigrateDataException
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
        players, players_info, cookies = [], [], []
        for player in self.need_migrate_player:
            try:
                await self.players_service.update(player)
            except StaleDataError:
                players.append(str(player.player_id))
        for player_info in self.need_migrate_player_info:
            try:
                await self.player_info_service.update(player_info)
            except StaleDataError:
                players_info.append(str(player_info.player_id))
        for cookie in self.need_migrate_cookies:
            try:
                await self.cookies_service.update(cookie)
            except StaleDataError:
                cookies.append(str(cookie.account_id))
        if any([players, players_info, cookies]):
            text = []
            if players:
                text.append(f"player 数据迁移失败 player_id {','.join(players)}")
            if players_info:
                text.append(f"player_info 数据迁移失败 player_id {','.join(players_info)}")
            if cookies:
                text.append(f"cookies 数据迁移失败 account_id {','.join(cookies)}")
            raise MigrateDataException("、".join(text))
        return True

    @staticmethod
    async def create_players(
        old_user_id: int,
        new_user_id: int,
        players_service: PlayersService,
    ) -> List[Player]:
        need_migrate, new_data = await AccountMigrate.filter_sql_data(
            Player,
            players_service.get_all_by_user_id,
            old_user_id,
            new_user_id,
            (Player.account_id, Player.player_id, Player.region),
        )
        for i in need_migrate:
            i.user_id = new_user_id
            if new_data:
                i.is_chosen = False
        return need_migrate

    @staticmethod
    async def create_players_info(
        old_user_id: int,
        new_user_id: int,
        player_info_service: PlayerInfoService,
    ) -> List[PlayerInfo]:
        need_migrate, _ = await AccountMigrate.filter_sql_data(
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
        need_migrate, _ = await AccountMigrate.filter_sql_data(
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
        self.players_service = players_service
        self.player_info_service = player_info_service
        self.cookies_service = cookies_service
        self.need_migrate_player = need_migrate_player
        self.need_migrate_player_info = need_migrate_player_info
        self.need_migrate_cookies = need_migrate_cookies
        return self
