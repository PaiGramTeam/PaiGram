from typing import Optional

import httpx

from utils.log import logger

__all__ = ["PbClient", "PbClientException"]


class PbClientException(Exception):
    pass


class PbClient:
    def __init__(self, pb_url: Optional[str] = None, pb_sunset: Optional[int] = None, pb_max_lines: int = 1000):
        """PbClient
        :param pb_url:
        :param pb_sunset: 自动销毁时间 单位为秒
        :param pb_max_lines:
        """
        self.client = httpx.AsyncClient()
        self.PB_API = pb_url
        self.sunset: int = pb_sunset
        self.private: bool = True
        self.max_lines: int = pb_max_lines

    @property
    def enabled(self) -> bool:
        return bool(self.PB_API)

    async def create_pb(self, content: str) -> Optional[str]:
        try:
            return await self._create_pb(content)
        except Exception as exc:
            raise PbClientException from exc

    async def _create_pb(self, content: str) -> Optional[str]:
        if not self.PB_API:
            return None
        content = "\n".join(content.splitlines()[-self.max_lines :]) + "\n"
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
        return result.headers.get("location")
