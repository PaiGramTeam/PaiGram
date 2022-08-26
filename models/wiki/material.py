from typing import List, Optional, Iterator

from models.wiki.base import WikiModel, Model

__all__ = ['Material']


class Material(WikiModel):
    """材料"""
    type: str
    """类型"""
    source: List[str]
    """获取方式"""
    description: str
    """秒速"""
    recipe: List["MaterialRecipe"]
    """合成材料"""
    series: Optional["MaterialSeries"]
    """系列"""


class MaterialRecipe(Model):
    """合成配方"""
    item: Material
    """材料"""
    value: int
    """材料数量"""


class MaterialSeries(Model):
    """系列材料

    例如 史莱姆凝液、史莱姆清 和 史莱姆原浆 是属于一个系列的
    根据材料的等级来存放：例如 史莱姆原浆 是 3 星材料，那么它将存放在 `level_3` 中

    """
    level_1: Optional[Material] = None
    level_2: Optional[Material] = None
    level_3: Optional[Material] = None
    level_4: Optional[Material] = None
    level_5: Optional[Material] = None

    def __iter__(self) -> Iterator[Material]:
        """生成这个系列的所有材料的迭代器"""
        return iter(filter(
            lambda x: x is not None, [self.level_1, self.level_2, self.level_3, self.level_4, self.level_5]
        ))

    def __getitem__(self, index: int) -> Optional[Material]:
        """获取这个系列的第某个材料

        不会包含空值，例如该系列只有等级为 2-5 的材料，则当 `index` 为 1 的时候，会返回 `level_2`

        Args:
            index (:obj:int): 材料的索引
        """
        return list(self.__iter__())[index + 1]
