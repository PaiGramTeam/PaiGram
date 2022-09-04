from utils.baseobject import BaseObject


class Skill(BaseObject):
    """
    技能信息
    """

    def __init__(self, skill_id: int = 0, name: str = "", level: int = 0, icon: str = ""):
        """
        :param skill_id: 技能ID
        :param name: 技能名称
        :param level: 技能等级
        :param icon: 技能图标
        """
        self.icon = icon
        self.level = level
        self.name = name
        self.skill_id = skill_id

    __slots__ = ("skill_id", "name", "level", "icon")
