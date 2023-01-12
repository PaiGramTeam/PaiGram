import logging

import pytest
import pytest_asyncio
from flaky import flaky

from modules.apihelper.client.components.abyss import AbyssTeam
from modules.apihelper.models.genshin.abyss import TeamRateResult, TeamRate, FullTeamRate

LOGGER = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def abyss_team_data():
    _abyss_team_data = AbyssTeam()
    yield _abyss_team_data
    await _abyss_team_data.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_abyss_team_data(abyss_team_data: AbyssTeam):
    team_data = await abyss_team_data.get_data()
    assert isinstance(team_data, TeamRateResult)
    assert isinstance(team_data.rate_list_up[0], TeamRate)
    assert isinstance(team_data.rate_list_up[-1], TeamRate)
    assert isinstance(team_data.rate_list_down[0], TeamRate)
    assert isinstance(team_data.rate_list_down[-1], TeamRate)
    assert team_data.user_count > 0
    team_data.sort(["迪奥娜", "芭芭拉", "凯亚", "琴"])
    assert isinstance(team_data.rate_list_full[0], FullTeamRate)
    assert isinstance(team_data.rate_list_full[-1], FullTeamRate)
    random_team = team_data.random_team()[0]
    assert isinstance(random_team, FullTeamRate)
    member_up = {i.name for i in random_team.up.formation}
    member_down = {i.name for i in random_team.down.formation}
    assert not member_up & member_down
    for i in team_data.rate_list_full[0].down.formation:
        LOGGER.info("rate down info:name %s star %s", i.name, i.star)
    for i in team_data.rate_list_full[0].up.formation:
        LOGGER.info("rate up info:name %s star %s", i.name, i.star)
