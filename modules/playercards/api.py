from typing import Union

import httpx
from httpx import HTTPError

from modules.apihelper.helpers import get_headers
from modules.playercards.error import ResponseError, PlayerInfoDataNotFind, ShowAvatarInfoNotFind, AvatarInfoNotFind, \
    HTTPResponseError


class PlayerCardsAPI:
    UI_URL = "https://enka.shinshin.moe/ui/"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())

    async def get_data(self, uid: Union[str, int]):
        url = f"https://enka.network/u/{uid}/__data.json"
        try:
            response = await self.client.get(url)
        except HTTPError:
            raise HTTPResponseError
        if response.status_code != 200:
            raise ResponseError(response.status_code)
        json_data = response.json()
        if not json_data.get("playerInfo"):
            raise PlayerInfoDataNotFind(uid)
        if not json_data.get("playerInfo").get("showAvatarInfoList"):
            raise ShowAvatarInfoNotFind(uid)
        if not json_data.get("avatarInfoList"):
            raise AvatarInfoNotFind(uid)
        return json_data
