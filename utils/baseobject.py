import json
from copy import deepcopy
from typing import Dict, Union, Optional, List

from utils.models.types import JSONDict


class BaseObject:
    """
    大多数数据对象的基础类型
    """

    def __new__(cls, *args: object, **kwargs: object) -> "BaseObject":
        instance = super().__new__(cls)
        return instance

    def __str__(self) -> str:
        return str(self.to_dict())

    def __getitem__(self, item: str) -> object:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(
                f"Objects of type {self.__class__.__name__} don't have an attribute called "
                f"`{item}`."
            ) from exc

    def __getstate__(self) -> Dict[str, Union[str, object]]:
        return self._get_attrs(include_private=True, recursive=False)

    def __setstate__(self, state: dict) -> None:
        for key, val in state.items():
            setattr(self, key, val)

    def __deepcopy__(self, memodict: dict = None):
        if memodict is None:
            memodict = {}
        cls = self.__class__
        result = cls.__new__(cls)  # 创建新实例
        attrs = self._get_attrs(include_private=True)  # 获取其所有属性

        for k in attrs:  # 在DeepCopy对象中设置属性
            setattr(result, k, deepcopy(getattr(self, k), memodict))
        return result

    # 添加插槽可减少内存使用，并允许更快的属性访问
    __slots__ = ()

    def _get_attrs(self, include_private: bool = False, recursive: bool = False, ) -> Dict[str, Union[str, object]]:
        data = {}
        if not recursive:
            try:
                # __dict__ 具有来自超类的属性，因此无需在下面的for循环中输入
                data.update(self.__dict__)
            except AttributeError:
                pass
        # 我们希望使用self获取类的所有属性，但如果使用 self.__slots__ ，仅包括该类本身使用的属性，而不是它的超类
        # 因此，我们得到它的MRO，然后再得到它们的属性
        # 使用“[：-1]”切片排除了“object”类
        for cls in self.__class__.__mro__[:-1]:
            for key in cls.__slots__:  # 忽略 属性已定义
                if not include_private and key.startswith("_"):
                    continue

                value = getattr(self, key, None)
                if value is not None:
                    if recursive and hasattr(value, "to_dict"):
                        data[key] = value.to_dict()
                    else:
                        data[key] = value
                elif not recursive:
                    data[key] = value

        return data

    @staticmethod
    def _parse_data(data: Optional[JSONDict]) -> Optional[JSONDict]:
        return None if data is None else data.copy()

    @classmethod
    def de_json(cls, data: Optional[JSONDict]):
        data = cls._parse_data(data)

        if data is None:
            return None

        if cls == BaseObject:
            return cls()
        return cls(**data)

    @classmethod
    def de_list(cls, data: Optional[List[JSONDict]]) -> List:
        if not data:
            return []

        return [cls.de_json(d) for d in data]

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self) -> JSONDict:
        return self._get_attrs(recursive=True)
