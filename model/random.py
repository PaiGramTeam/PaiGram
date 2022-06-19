import time
from numpy.random import Generator, MT19937


class MT19937_Random:
    """
    基于 numpy 实现的动态删除时间设计
                            ——MXtao_dada | 小男孩赛高！
    笑死，不然你猜猜为啥 requirements.txt 有 numpy ？
                            ——洛水居室
    笑死，虽然说我是写的 ）
    不得不说让我想到一个事情，万一以用户的ID做随机数种子呢，这样就可以决定某个账户一开始就是非洲或者欧洲 )
    """

    def __init__(self):
        self.send_time = time.time()
        self.generator = Generator(MT19937(int(self.send_time)))

    def random(self, low: int, high: int) -> int:
        if self.send_time + 24 * 60 * 60 >= time.time():  # 86400秒后刷新随机数种子
            self.send_time = time.time()
            self.generator = Generator(MT19937(int(self.send_time)))
        return int(self.generator.uniform(low, high))
