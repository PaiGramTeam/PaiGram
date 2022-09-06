from pydantic import BaseModel


class FetterInfo(BaseModel):
    """好感度信息"""
    level: int = 0  # 好感度等级
