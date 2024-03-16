from collections.abc import ItemsView

from pydantic import BaseModel as PydanticBaseModel

try:
    import ujson as json
except ImportError:
    import json


class BaseModel(PydanticBaseModel):
    class Config:
        json_loads = json.loads


class ItemData(BaseModel):
    id: str  # ID
    name: str  # 名称
    rarity: int  # 星级
    icon: str  # 图标
    level: int | None = None  # 等级


class MaterialData(BaseModel):
    icon: str
    rarity: int


class AvatarData(ItemData):
    constellation: int | None = None  # 命座
    skills: list[int] | None = None  # 天赋等级


class WeaponData(ItemData):
    refinement: int | None = None  # 精炼度
    avatar_icon: str | None = None  # 武器使用者图标


class AreaData(BaseModel):
    name: str  # 区域名
    material_name: str  # 区域的材料系列名
    materials: list[MaterialData] = []  # 区域材料
    avatars: list[AvatarData] = []
    weapons: list[WeaponData] = []

    @property
    def items(self) -> list[AvatarData | WeaponData]:
        """可培养的角色或武器"""
        return self.avatars or WeaponData


class RenderData(BaseModel):
    title: str  # 页面标题，主要用于显示星期几
    time: str  # 页面时间
    uid: str | None = None  # 用户UID
    character: list[AreaData] = []  # 角色数据
    weapon: list[AreaData] = []  # 武器数据

    def __getitem__(self, item):
        return self.__getattribute__(item)


class UserOwned(BaseModel):
    avatars: dict[str, AvatarData] = {}
    """角色 ID 到角色对象的映射"""
    weapons: dict[str, list[WeaponData]] = {}
    """用户同时可以拥有多把同名武器，因此是 ID 到 list 的映射"""


class FarmingData(BaseModel):
    weekday: str
    areas: list[AreaData]

    def items(self) -> ItemsView:
        return self.dict().items()


class FullFarmingData(BaseModel):
    __root__: dict[int, FarmingData] = {}

    def __bool__(self) -> bool:
        return bool(self.__root__)

    def weekday(self, weekday: int) -> FarmingData | dict:
        return self.__root__.get(weekday, {})
