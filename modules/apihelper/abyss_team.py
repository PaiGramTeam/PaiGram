import time
from typing import List, Optional

import httpx
from pydantic import BaseModel, parse_obj_as, validator


class Member(BaseModel):
    star: int
    attr: str
    name: str


class TeamRate(BaseModel):
    rate: float
    formation: List[Member]
    ownerNum: Optional[int]

    @validator('rate', pre=True)
    def str2float(cls, v):  # pylint: disable=R0201
        return float(v.replace('%', '')) / 100.0 if isinstance(v, str) else v


class FullTeamRate(BaseModel):
    up: TeamRate
    down: TeamRate
    ownerNum: Optional[int]

    @property
    def rate(self) -> float:
        return self.up.rate + self.down.rate


class TeamRateResult(BaseModel):
    rateListUp: List[TeamRate]
    rateListDown: List[TeamRate]
    userCount: int

    @property
    def rateListFull(self) -> List[FullTeamRate]:
        rateListFull = []
        for teamUp in self.rateListUp:
            for teamDown in self.rateListDown:
                if {member.name for member in teamUp.formation} & {member.name for member in teamDown.formation}:
                    continue
                self.rateListFull.append(FullTeamRate(up=teamUp, down=teamDown))
        return rateListFull

    def sort(self, characters: List[str]):
        for team in self.rateListFull:
            team.ownerNum = sum([1 for member in team.up.formation + team.down.formation if member.name in characters])
        self.rateListFull.sort(key=lambda x: (x.ownerNum / 4 * x.rate), reverse=True)


class AbyssTeamData:
    TEAM_RATE_API = "https://www.youchuang.fun/gamerole/formationRate"
    HEADERS = {
        'Host': 'www.youchuang.fun',
        'Referer': 'https://servicewechat.com/wxce4dbe0cb0f764b3/91/page-frame.html',
        'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
                      'Mobile/15E148 MicroMessenger/8.0.20(0x1800142f) NetType/WIFI Language/zh_CN',
        'content-type': 'application/json'
    }
    VERSION = "3.1"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.HEADERS)
        self.time = 0
        self.data = None
        self.ttl = 10 * 60

    async def get_data(self) -> TeamRateResult:
        if self.data is None or self.time + self.ttl < time.time():
            data_up = await self.client.post(self.TEAM_RATE_API, json={"version": self.VERSION, "layer": 1})
            data_up_json = data_up.json()["result"]
            data_down = await self.client.post(self.TEAM_RATE_API, json={"version": self.VERSION, "layer": 2})
            data_down_json = data_down.json()["result"]
            self.data = TeamRateResult(rateListUp=parse_obj_as(List[TeamRate], data_up_json["rateList"]),
                                       rateListDown=parse_obj_as(List[TeamRate], data_down_json["rateList"]),
                                       userCount=data_up_json["userCount"])
            self.time = time.time()
        return self.data.copy(deep=True)

    async def close(self):
        await self.client.aclose()
