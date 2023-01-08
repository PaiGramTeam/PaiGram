import pytest

from core.config import config
from core.dependence.mysql import MySQL
from core.services.players import PlayersService
from core.services.players.models import PlayersDataBase, RegionEnum
from core.services.players.repositories import PlayersRepository

mysql = MySQL.from_config(config=config)
repository = PlayersRepository(mysql)
service = PlayersService(repository)

data = PlayersDataBase(
    user_id=1,
    account_id=2,
    player_id=3,
    nickname="nickname",
    signature="signature",
    hand_image=4,
    name_card_id=5,
    waifu_id=6,
    region=RegionEnum.HYPERION,
    is_chosen=1,
)


@pytest.mark.asyncio
async def test_add_player():
    await service.add(data)
