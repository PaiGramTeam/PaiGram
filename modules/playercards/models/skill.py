from pydantic import BaseModel


class Skill(BaseModel):
    """技能信息"""
    skill_id: int = 0  # 技能ID
    name: str = ""  # 技能名称
    level: int = 0  # 技能等级
    icon: str = ""  # 技能图标
