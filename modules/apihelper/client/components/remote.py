from typing import List, Dict

from httpx import AsyncClient, HTTPError

from metadata.scripts.metadatas import RESOURCE_DEFAULT_PATH


class Remote:
    """拉取云控资源"""

    BASE_URL = f"https://raw.githubusercontent.com/{RESOURCE_DEFAULT_PATH}"
    CALENDAR = f"{BASE_URL}calendar.json"
    BIRTHDAY = f"{BASE_URL}birthday.json"
    MATERIAL = f"{BASE_URL}roles_material.json"

    @staticmethod
    async def get_remote_calendar() -> Dict[str, Dict]:
        """获取云端日历"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.CALENDAR)
                if req.status_code == 200:
                    return req.json()
                return {}
        except HTTPError:
            return {}

    @staticmethod
    async def get_remote_birthday() -> Dict[str, List[str]]:
        """获取云端生日"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.BIRTHDAY)
                if req.status_code == 200:
                    return req.json()
                return {}
        except HTTPError:
            return {}

    @staticmethod
    async def get_remote_material() -> Dict[str, List[str]]:
        """获取云端角色材料"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.MATERIAL)
                if req.status_code == 200:
                    return req.json()
                return {}
        except HTTPError:
            return {}
