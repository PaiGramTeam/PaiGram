import logging

import pytest
import pytest_asyncio
from flaky import flaky

from modules.apihelper.abyss_team import AbyssTeamData, TeamRateResult, TeamRate, FullTeamRate

LOGGER = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def abyss_team_data():
    _abyss_team_data = AbyssTeamData()
    yield _abyss_team_data
    await _abyss_team_data.close()


# noinspection PyShadowingNames
@pytest.mark.asyncio
@flaky(3, 1)
async def test_abyss_team_data(abyss_team_data: AbyssTeamData):
    team_data = await abyss_team_data.get_data()
    assert isinstance(team_data, TeamRateResult)
    assert isinstance(team_data.rate_list_up[0], TeamRate)
    assert isinstance(team_data.rate_list_up[-1], TeamRate)
    assert isinstance(team_data.rate_list_down[0], TeamRate)
    assert isinstance(team_data.rate_list_down[-1], TeamRate)
    assert team_data.user_count > 0
    for i in team_data.rate_list_up[0].formation:
        LOGGER.info("rate down info:name %s star %s", i.name, i.star)
    for i in team_data.rate_list_down[0].formation:
        LOGGER.info("rate up info:name %s star %s", i.name, i.star)
    team_data.sort(["迪奥娜", "芭芭拉", "凯亚", "琴"])
    assert isinstance(team_data.rate_list_full[0], FullTeamRate)
    assert isinstance(team_data.rate_list_full[-1], FullTeamRate)
    memberUp = {i.name for i in team_data.rate_list_full[0].up.formation}
    memberDown = {i.name for i in team_data.rate_list_full[0].down.formation}
    assert memberUp & memberDown == set()
