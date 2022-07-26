from enum import Enum

from model.gacha.common import ItemParamData


class BannerType(Enum):
    STANDARD = 1
    EVENT = 2
    WEAPON = 3


class GachaBanner:
    def __init__(self):
        self.gachaType: int = 0
        self.scheduleId: int = 0
        self.prefabPath: str = ""
        self.previewPrefabPath: str = ""
        self.titlePath: str = ""
        self.costItemId = 0
        self.costItemAmount = 1
        self.costItemId10 = 0
        self.costItemAmount10 = 10
        self.beginTime: int = 0
        self.endTime: int = 0
        self.sortId: int = 0
        self.rateUpItems4 = {}
        self.rateUpItems5 = {}
        self.fallbackItems3 = {11301, 11302, 11306, 12301, 12302, 12305, 13303, 14301, 14302, 14304, 15301, 15302,
                               15304}
        self.fallbackItems4Pool1 = {1014, 1020, 1023, 1024, 1025, 1027, 1031, 1032, 1034, 1036, 1039, 1043, 1044, 1045,
                                    1048, 1053, 1055, 1056, 1064}
        self.fallbackItems4Pool2 = {11401, 11402, 11403, 11405, 12401, 12402, 12403, 12405, 13401, 13407, 14401, 14402,
                                    14403, 14409, 15401, 15402, 15403, 15405}
        self.fallbackItems5Pool1 = {1003, 1016, 1042, 1035, 1041}
        self.fallbackItems5Pool2 = {11501, 11502, 12501, 12502, 13502, 13505, 14501, 14502, 15501, 15502}
        self.removeC6FromPool = False
        self.autoStripRateUpFromFallback = True
        self.weights4 = {{1, 510}, {8, 510}, {10, 10000}}
        self.weights5 = {{1, 75}, {73, 150}, {90, 10000}}
        self.poolBalanceWeights4 = {{1, 255}, {17, 255}, {21, 10455}}
        self.poolBalanceWeights5 = {{1, 30}, {147, 150}, {181, 10230}}
        self.eventChance4 = 50
        self.eventChance5 = 50
        self.bannerType = BannerType.STANDARD
        self.rateUpItems1 = {}
        self.rateUpItems2 = {}
        self.eventChance = -1
        self.costItem = 0

    def getGachaType(self):
        return self.gachaType

    def getCost(self, numRolls: int):
        """
        获取消耗的Item
        :param numRolls:
        :return:
        """
        if numRolls == 1:
            return ItemParamData()
        elif numRolls == 10:
            return ItemParamData(self.costItemId10 if self.costItemId10 > 0 else self.getCostItem(),
                                 self.costItemAmount10)
        return ItemParamData()

    def getCostItem(self):
        return self.costItem if self.costItem > 0 else self.costItemId
