import contextlib
from typing import List


def lerp(x: int, x_y_array) -> int:
    with contextlib.suppress(KeyError, IndexError):
        if x <= x_y_array[0][0]:
            return x_y_array[0][1]
        if x >= x_y_array[-1][0]:
            return x_y_array[-1][1]
        for index, _ in enumerate(x_y_array):
            if x == x_y_array[index + 1][0]:
                return x_y_array[index + 1][1]
            if x < x_y_array[index + 1][0]:
                position = x - x_y_array[index][0]
                full_dist = x_y_array[index + 1][0] - x_y_array[index][0]
                if full_dist == 0:
                    return position
                prev_value = x_y_array[index][1]
                full_delta = x_y_array[index + 1][1] - prev_value
                return int(prev_value + ((position * full_delta) / full_dist))
    return 0


def set_subtract(minuend: List[int], subtrahend: List[int]) -> List[int]:
    return [i for i in minuend if i not in subtrahend]
