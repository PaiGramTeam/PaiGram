from models.baseobject import BaseObject


class Talent(BaseObject):
    """
    命座
    """

    def __init__(self, talent_id: int = 0, name: str = "", icon: str = ""):
        """
        :param talent_id: 命座ID
        :param name: 命座名字
        :param icon: 图标
        """
        self.icon = icon
        self.name = name
        self.talent_id = talent_id

    __slots__ = ("talent_id", "name", "icon")
