from typing import List


class TalentMaterials:
    def __init__(self, amount: List[int]):
        self.amount = amount

    def cal_materials(self) -> List[int]:
        """
        :return: [摩拉，天赋书x3，怪物素材x3，皇冠，周本素材]
        """
        cost = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        cost_list = [
            [0, 0, 0, 0, 0, 0, 0, 0, 0],
            [12500, 3, 0, 0, 6, 0, 0, 0, 0],
            [17500, 0, 2, 0, 0, 3, 0, 0, 0],
            [25000, 0, 4, 0, 0, 4, 0, 0, 0],
            [30000, 0, 6, 0, 0, 6, 0, 0, 0],
            [37500, 0, 9, 0, 0, 9, 0, 0, 0],
            [120000, 0, 0, 4, 0, 0, 4, 0, 1],
            [260000, 0, 0, 6, 0, 0, 6, 0, 1],
            [450000, 0, 0, 12, 0, 0, 9, 0, 2],
            [700000, 0, 0, 16, 0, 0, 12, 1, 2],
        ]
        for i in self.amount:
            for level in range(1, i):
                cost = list(map(lambda x: x[0] + x[1], zip(cost, cost_list[level])))
        return cost
