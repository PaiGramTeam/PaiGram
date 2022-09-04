from modules.baseobject import BaseObject


class FetterInfo(BaseObject):
    """
    好感度信息
    """

    def __init__(self, level: int = 0):
        """
        :param level: 等级
        """
        self.level = level

    __slots__ = ("level",)
