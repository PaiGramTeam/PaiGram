from typing import List, Dict

from httpx import AsyncClient

from metadata.scripts.metadatas import RESOURCE_FAST_URL, RESOURCE_FightPropRule_URL
from utils.log import logger


class Remote:
    """拉取云控资源"""

    BASE_URL = RESOURCE_FAST_URL
    CALENDAR = f"{BASE_URL}calendar.json"
    BIRTHDAY = f"{BASE_URL}birthday.json"
    MATERIAL = f"{BASE_URL}roles_material.json"
    RULE = f"{RESOURCE_FightPropRule_URL}FightPropRule_genshin.json"

    @staticmethod
    async def get_remote_calendar() -> Dict[str, Dict]:
        """获取云端日历"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.CALENDAR)
                if req.status_code == 200:
                    return req.json()
                return {}
        except Exception as exc:
            logger.error("获取云端日历失败: %s", exc_info=exc)
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
        except Exception as exc:
            logger.error("获取云端生日失败: %s", exc_info=exc)
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
        except Exception as exc:
            logger.error("获取云端角色材料失败: %s", exc_info=exc)
            return {}

    @staticmethod
    async def get_fight_prop_rule_data() -> Dict[str, Dict[str, float]]:
        """获取云端圣遗物评分规则"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.RULE)
                if req.status_code == 200:
                    return req.json()
                return {}
        except Exception as exc:
            logger.error("获取云端圣遗物评分规则失败: %s", exc_info=exc)
            return {}
