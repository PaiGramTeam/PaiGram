import time
from typing import List, Optional, Any

import httpx
from pydantic import BaseModel, parse_obj_as, validator


class Member(BaseModel):
    star: int
    attr: str
    name: str


class TeamRate(BaseModel):
    rate: float
    formation: List[Member]
    owner_num: Optional[int]

    @validator("rate", pre=True)
    def str2float(cls, v):  # pylint: disable=R0201
        return float(v.replace("%", "")) / 100.0 if isinstance(v, str) else v


class FullTeamRate(BaseModel):
    up: TeamRate
    down: TeamRate
    owner_num: Optional[int]
    nice: Optional[float]

    @property
    def rate(self) -> float:
        return (self.up.rate + self.down.rate) / 2


class TeamRateResult(BaseModel):
    version: str
    rate_list_up: List[TeamRate]
    rate_list_down: List[TeamRate]
    rate_list_full: List[FullTeamRate] = []
    user_count: int

    def __init__(self, **data: Any):
        super().__init__(**data)
        for team_up in self.rate_list_up:
            for team_down in self.rate_list_down:
                if {member.name for member in team_up.formation} & {member.name for member in team_down.formation}:
                    continue
                self.rate_list_full.append(FullTeamRate(up=team_up, down=team_down))

    def sort(self, characters: List[str]):
        for team in self.rate_list_full:
            team.owner_num = sum(member.name in characters for member in team.up.formation + team.down.formation)
            team.nice = team.owner_num / 8 + team.rate
        self.rate_list_full.sort(key=lambda x: x.nice, reverse=True)

    def random_team(self) -> List[FullTeamRate]:
        data: List[FullTeamRate] = []
        for team in self.rate_list_full:
            add = True
            for team_ in data:
                if {member.name for member in team.up.formation} & {member.name for member in team_.up.formation}:
                    add = False
                    break
                if {member.name for member in team.down.formation} & {member.name for member in team_.down.formation}:
                    add = False
                    break
            if add:
                data.append(team)
                if len(data) >= 3:
                    break
        return data


class AbyssTeamData:
    TEAM_RATE_API = "https://www.youchuang.fun/gamerole/formationRate"
    HEADERS = {
        "Host": "www.youchuang.fun",
        "Referer": "https://servicewechat.com/wxce4dbe0cb0f764b3/91/page-frame.html",
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Mobile/15E148 MicroMessenger/8.0.20(0x1800142f) NetType/WIFI Language/zh_CN",
        "content-type": "application/json",
    }
    VERSION = "3.2"

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
            self.data = TeamRateResult(
                version=self.VERSION,
                rate_list_up=parse_obj_as(List[TeamRate], data_up_json["rateList"]),
                rate_list_down=parse_obj_as(List[TeamRate], data_down_json["rateList"]),
                user_count=data_up_json["userCount"],
            )
            self.time = time.time()
        return self.data.copy(deep=True)

    async def close(self):
        await self.client.aclose()
