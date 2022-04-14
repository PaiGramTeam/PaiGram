import random
from enum import Enum


class GACHA_TYPE(Enum):
    activity = 301  # 限定卡池
    activity2 = 400  # 限定卡池
    weapon = 302  # 武器卡池
    permanent = 200  # 常驻卡池


class WishCountInfo:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.five_stars_count: int = 1
        self.four_stars_count: int = 1
        self.is_up: bool = False
        self.maximum_fate_points: int = 0


def character_probability(rank, count):
    ret = 0
    if rank == 5 and count <= 73:
        ret = 60
    elif rank == 5 and count >= 74:
        ret = 60 + 600 * (count - 73)
    elif rank == 4 and count <= 8:
        ret = 510
    elif rank == 4 and count >= 9:
        ret = 510 + 5100 * (count - 8)
    return ret


def weapon_probability(rank, count):
    ret = 0
    if rank == 5 and count <= 62:
        ret = 70
    elif rank == 5 and count <= 73:
        ret = 70 + 700 * (count - 62)
    elif rank == 5 and count >= 74:
        ret = 7770 + 350 * (count - 73)
    elif rank == 4 and count <= 7:
        ret = 600
    elif rank == 4 and count == 8:
        ret = 6600
    elif rank == 4 and count >= 9:
        ret = 6600 + 3000 * (count - 8)
    return ret


def is_character_gacha(gacha_type: GACHA_TYPE) -> bool:
    return gacha_type == GACHA_TYPE.activity or gacha_type == GACHA_TYPE.activity2 or gacha_type == GACHA_TYPE.permanent


def random_int():
    return random.randint(0, 10000)


def get_is_up(rank: int, count: WishCountInfo, gacha_type: GACHA_TYPE):
    if gacha_type == GACHA_TYPE.permanent:
        return False
    elif gacha_type == GACHA_TYPE.weapon:
        return random_int() <= 7500
    else:
        return random_int() <= 5000 or (rank == 5 and count.is_up)


def get_rank(count: WishCountInfo, gacha_type: GACHA_TYPE):
    value = random_int()
    probability_fn = is_character_gacha(gacha_type) and character_probability or weapon_probability
    index_5 = probability_fn(5, count.five_stars_count)
    index_4 = probability_fn(4, count.four_stars_count) + index_5
    if value <= index_5:
        return 5
    elif value <= index_4:
        return 4
    else:
        return 3


def get_one(count: WishCountInfo, gacha_info: dict, weapon_name: str = "") -> dict:
    gacha_type = GACHA_TYPE(gacha_info["gacha_type"])
    rank = get_rank(count, gacha_type)
    is_up = get_is_up(rank, count, gacha_type)
    if rank == 5:
        count.five_stars_count = 1
        if is_up:
            data = random.choice(gacha_info["r5_up_items"])
        else:
            data = random.choice(gacha_info["r5_prob_list"])
        if gacha_type == GACHA_TYPE.weapon:
            if data["item_name"] == weapon_name:
                count.maximum_fate_points = 0
            elif count.maximum_fate_points == 2:
                count.maximum_fate_points = 0
                for temp_item in gacha_info["r5_up_items"]:
                    if temp_item["item_name"] == weapon_name:
                        data = temp_item
                        break
            else:
                count.maximum_fate_points += 1
        if gacha_type == GACHA_TYPE.activity or gacha_type == GACHA_TYPE.activity2 or gacha_type == GACHA_TYPE.weapon:
            count.is_up = not is_up
        return {
            "item_type": data["item_type"],
            "item_name": data["item_name"],
            "rank": 5,
        }
    elif rank == 4:
        count.five_stars_count += 1
        count.four_stars_count = 1
        if is_up:
            data = random.choice(gacha_info["r4_up_items"])
        else:
            data = random.choice(gacha_info["r4_prob_list"])
        return {
            "item_type": data["item_type"],
            "item_name": data["item_name"],
            "rank": 4,
        }
    elif rank == 3:
        count.five_stars_count += 1
        count.four_stars_count += 1
        data = random.choice(gacha_info["r3_prob_list"])
        return {
            "item_type": data["item_type"],
            "item_name": data["item_name"],
            "rank": 3,
        }
    else:
        raise ValueError("rank value error")
