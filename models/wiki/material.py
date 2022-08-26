from typing import List, Optional, Iterator

from models.wiki.base import WikiModel, Model

__all__ = ['Material']


class Material(WikiModel):
    """材料"""
    """类型"""
    type: str

    """获取方式"""
    source: List[str]

    """秒速"""
    description: str

    """合成材料"""
    recipe: List["MaterialRecipe"]

    """系列"""
    series: Optional["MaterialSeries"]


class MaterialRecipe(Model):
    """合成配方"""
    """材料"""
    item: Material

    """材料数量"""
    value: int


class MaterialSeries(Model):
    """系列材料"""
    level_1: Optional[Material] = None
    level_2: Optional[Material] = None
    level_3: Optional[Material] = None
    level_4: Optional[Material] = None
    level_5: Optional[Material] = None

    def __iter__(self) -> Iterator[Material]:
        return iter(filter(
            lambda x: x is not None, [self.level_1, self.level_2, self.level_3, self.level_4, self.level_5]
        ))

    def __getitem__(self, index: int) -> Optional[Material]:
        if isinstance(index, int):
            return eval(f"self.level_{index}")
