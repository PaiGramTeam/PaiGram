from typing import Union

from pydantic import BaseModel, validator

from modules.playercards.models.fightprop import FightProp


class GameItem(BaseModel):
    item_id: int = 0
    type: Union[FightProp, str] = ""
    value: Union[str, int, float] = 0

    @validator("type")
    def type_rule(cls, _type):
        if _type == "":
            raise ValueError
        if isinstance(_type, str):
            try:
                _type = FightProp.__getitem__(_type)
            except ValueError:
                _type = FightProp(_type)
        elif isinstance(_type, FightProp):
            _type = _type
        else:
            raise TypeError
        return _type

    @validator("value")
    def value_rule(cls, value):
        if isinstance(value, str):
            return eval(value)
        return value

    @property
    def name(self):
        return self.type.value
