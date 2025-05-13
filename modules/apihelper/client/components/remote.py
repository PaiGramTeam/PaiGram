from typing import Dict, Any

from httpx import AsyncClient

from metadata.scripts.metadatas import RESOURCE_FightPropRule_URL
from utils.log import logger


class Remote:
    """拉取云控资源"""

    RULE = f"{RESOURCE_FightPropRule_URL}FightPropRule_genshin.json"
    DAMAGE = f"{RESOURCE_FightPropRule_URL}GenshinDamageRule.json"
    GCSIM = f"{RESOURCE_FightPropRule_URL}gcsim.json"

    @staticmethod
    async def get_fight_prop_rule_data() -> Dict[str, Dict[str, float]]:
        """获取云端圣遗物评分规则"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.RULE)
                if req.status_code == 200:
                    return req.json()
                return {}
        except Exception as exc:  # skipcq: PYL-W0703
            logger.error("获取云端圣遗物评分规则失败: %s", exc_info=exc)
            return {}

    @staticmethod
    async def get_damage_data() -> Dict[str, Any]:
        """获取云端伤害计算规则"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.DAMAGE)
                if req.status_code == 200:
                    return req.json()
                return {}
        except Exception as exc:  # skipcq: PYL-W0703
            logger.error("获取云端伤害计算规则失败: %s", exc_info=exc)
            return {}

    @staticmethod
    async def get_gcsim_scripts() -> Dict[str, str]:
        """获取云端 gcsim 脚本"""
        try:
            async with AsyncClient() as client:
                req = await client.get(Remote.GCSIM)
                if req.status_code == 200:
                    return req.json()
                return {}
        except Exception as exc:  # skipcq: PYL-W0703
            logger.error("获取云端 gcsim 脚本失败: %s", exc_info=exc)
            return {}
