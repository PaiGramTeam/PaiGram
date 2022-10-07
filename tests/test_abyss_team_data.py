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
    assert isinstance(team_data.rateListUp[0], TeamRate)
    assert isinstance(team_data.rateListUp[-1], TeamRate)
    assert isinstance(team_data.rateListDown[0], TeamRate)
    assert isinstance(team_data.rateListDown[-1], TeamRate)
    assert team_data.userCount > 0
    for i in team_data.rateListUp[0].formation:
        LOGGER.info("rate down info:name %s star %s", i.name, i.star)
    for i in team_data.rateListDown[0].formation:
        LOGGER.info("rate up info:name %s star %s", i.name, i.star)
    assert isinstance(team_data.rateListFull[0], FullTeamRate)
    assert isinstance(team_data.rateListFull[-1], FullTeamRate)
    assert team_data.rateListFull[0].rate > 1
    assert team_data.rateListFull[-1].rate > 1
