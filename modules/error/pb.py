from typing import Optional

import httpx

from core.config import config
from utils.log import logger


class PbClient:
    def __init__(self):
        self.client = httpx.AsyncClient()
        self.PB_API = config.error.pb_url
        self.sunset: int = config.error.pb_sunset  # 自动销毁时间 单位为秒
        self.private: bool = True
        self.max_lines: int = config.error.pb_max_lines

    async def create_pb(self, content: str) -> Optional[str]:
        if not self.PB_API:
            return None
        logger.info("正在上传日记到 pb")
        content = "\n".join(content.splitlines()[-self.max_lines:]) + "\n"
        data = {
            "c": content,
        }
        if self.private:
            data["p"] = "1"
        if self.sunset:
            data["sunset"] = self.sunset
        result = await self.client.post(self.PB_API, data=data)
        if result.is_error:
            logger.warning("上传日记到 pb 失败 status_code[%s]", result.status_code)
            return None
        logger.success("上传日记到 pb 成功")
        return result.headers.get("location")
