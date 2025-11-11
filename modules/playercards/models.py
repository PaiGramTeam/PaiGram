from datetime import datetime

from enkanetwork import EnkaNetworkResponse as NetworkResponse, CharacterInfo
from pydantic import Field

__all__ = (
    "EnkaCharacterInfo",
    "EnkaNetworkResponse",
)


class EnkaCharacterInfo(CharacterInfo):
    pai_refresh_time: int | None = None

    def pai_refresh_time_str(self) -> str:
        timestamp = self.pai_refresh_time or 0
        if not timestamp:
            return "N/A"
        time = datetime.fromtimestamp(timestamp)
        return time.strftime("%Y-%m-%d %H:%M:%S")


class EnkaNetworkResponse(NetworkResponse):
    characters: list[EnkaCharacterInfo] = Field(None, alias="avatarInfoList")
