from modules.playercards.models.fightprop import FightProp


def _de_item_rule(_item_rule_data: dict):
    __item_rule: dict = {}
    for key, values in _item_rule_data.items():
        _data = []
        for value in values:
            try:
                _data.append(FightProp(value))
            except ValueError:
                pass
        __item_rule[key] = _data
    return __item_rule
