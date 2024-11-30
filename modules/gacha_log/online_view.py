from pathlib import Path
from typing import Optional

import httpx
from httpx import URL
from httpx import HTTPError
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.helpers import create_deep_linked_url

from gram_core.basemodel import Settings, SettingsConfigDict
from modules.gacha_log.error import GachaLogWebNotConfigError, GachaLogWebUploadError, GachaLogNotFound


class GachaLogWebConfig(Settings):
    """抽卡记录在线查询配置"""

    url: Optional[str] = ""
    token: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="gacha_log_web_")


gacha_log_web_config = GachaLogWebConfig()
DEFAULT_POOL = "角色祈愿"


class GachaLogOnlineView:
    """抽卡记录在线查询"""

    gacha_log_path: Path

    @staticmethod
    def get_web_upload_button(bot_username: str):
        if not gacha_log_web_config.url:
            return None
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        ">> 查询详细信息 <<", url=create_deep_linked_url(bot_username, "gacha_log_online_view")
                    )
                ]
            ]
        )

    async def web_upload(self, user_id: str, uid: str) -> str:
        if not gacha_log_web_config.url:
            raise GachaLogWebNotConfigError
        file_path = self.gacha_log_path / f"{user_id}-{uid}.json"
        if not file_path.exists():
            raise GachaLogNotFound
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as file:
                try:
                    req = await client.post(
                        URL(gacha_log_web_config.url).join("upload"),
                        files={"file": file},
                        data={
                            "token": gacha_log_web_config.token,
                            "uid": uid,
                            "game": "genshin",
                        },
                    )
                    req.raise_for_status()
                except HTTPError as e:
                    raise GachaLogWebUploadError from e
                account_id = req.json()["account_id"]
                url = (
                    URL(gacha_log_web_config.url)
                    .join("gacha_log")
                    .copy_merge_params(
                        {
                            "account_id": account_id,
                            "banner_type": DEFAULT_POOL,
                            "rarities": "3,4,5",
                            "size": 100,
                            "page": 1,
                        }
                    )
                )
                return str(url)
