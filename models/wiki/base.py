import ujson as json
from pydantic import BaseConfig as PydanticBaseConfig, BaseModel as PydanticBaseModel

__all__ = ['Model', 'WikiModel']


class Model(PydanticBaseModel):
    """基类"""

    def __new__(cls, *args, **kwargs):
        # 让每次new的时候都解析
        cls.update_forward_refs()
        return super(Model, cls).__new__(cls)

    class Config(PydanticBaseConfig):
        # 使用 ujson 作为解析库
        json_dumps = json.dumps
        json_loads = json.loads


class WikiModel(Model):
    """wiki所用到的基类"""
    """ID"""
    id: int

    """名称"""
    name: str

    """星级"""
    rarity: int

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {super(WikiModel, self).__str__()}>"

    def __repr__(self) -> str:
        return self.__str__()
