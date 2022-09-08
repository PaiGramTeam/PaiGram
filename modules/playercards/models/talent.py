from pydantic import BaseModel


class Talent(BaseModel):
    """命座"""
    talent_id: int = 0
    name: str = ""
    icon: str = ""
