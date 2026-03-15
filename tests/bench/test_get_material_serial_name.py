from collections.abc import Iterable, Iterator

import pytest_benchmark.fixture
from arkowrapper import ArkoWrapper

import plugins.genshin.daily.material


# Old implementation
def get_material_serial_name(names: Iterable[str]) -> str:
    """
    获取材料的系列名，本质上是求字符串列表的最长子串
    如：「自由」的教导、「自由」的指引、「自由」的哲学，三者系列名为「『自由』」
    如：高塔孤王的破瓦、高塔孤王的残垣、高塔孤王的断片、高塔孤王的碎梦，四者系列名为「高塔孤王」
    TODO(xr1s): 感觉可以优化
    """

    def all_substrings(string: str) -> Iterator[str]:
        """获取字符串的所有连续字串"""
        length = len(string)
        for i in range(length):
            for j in range(i + 1, length + 1):
                yield string[i:j]

    result = []
    for name_a, name_b in ArkoWrapper(names).repeat(1).group(2).unique(list):
        for sub_string in all_substrings(name_a):
            if sub_string in ArkoWrapper(all_substrings(name_b)):
                result.append(sub_string)
    result = ArkoWrapper(result).sort(len, reverse=True)[0]
    chars = {"的": 0, "之": 0}
    for char, k in chars.items():
        result = result.split(char)[k]
    return result


def test_old_get_material_serial_name_decarabian(benchmark: pytest_benchmark.fixture.BenchmarkFixture):
    series = benchmark(
        get_material_serial_name,
        ["高塔孤王的破瓦", "高塔孤王的残垣", "高塔孤王的断片", "高塔孤王的碎梦"],
    )
    assert series == "高塔孤王"


def test_old_get_material_serial_name_freedom(benchmark: pytest_benchmark.fixture.BenchmarkFixture):
    series = benchmark(get_material_serial_name, ["「自由」的教导", "「自由」的指引", "「自由」的哲学"])
    assert series == "「自由」"


def test_new_get_material_serial_name_decarabian(benchmark: pytest_benchmark.fixture.BenchmarkFixture):
    series = benchmark(
        plugins.genshin.daily.material.get_material_serial_name,
        ["高塔孤王的破瓦", "高塔孤王的残垣", "高塔孤王的断片", "高塔孤王的碎梦"],
    )
    assert series == "高塔孤王"


def test_new_get_material_serial_name_freedom(benchmark: pytest_benchmark.fixture.BenchmarkFixture):
    series = benchmark(
        plugins.genshin.daily.material.get_material_serial_name,
        ["「自由」的教导", "「自由」的指引", "「自由」的哲学"],
    )
    assert series == "「自由」"
