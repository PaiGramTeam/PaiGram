from typing import List, Optional, Any

from pydantic import BaseModel, validator

__all__ = ("Member", "TeamRate", "FullTeamRate", "TeamRateResult")


class Member(BaseModel):
    star: int
    avatar: str
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
