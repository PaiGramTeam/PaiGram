"""此文件用于储存 honey impact 中的部分基础数据"""
import re
from typing import Any, Dict, List, Optional

import ujson as json

from utils.const import PROJECT_ROOT
from utils.typedefs import StrOrInt

__all__ = [
    'HONEY_DATA',
    'AVATAR_DATA', 'WEAPON_DATA',
    'role_to_icon_name', 'weapon_to_icon_name',
]

data_dir = PROJECT_ROOT.joinpath('metadata/data/')


def _get_content(file_name: str) -> str:
    with open(data_dir.joinpath(file_name), encoding='utf-8') as file:
        return file.read()


HONEY_DATA: Dict[str, Dict[StrOrInt, List[str]]] = json.loads(_get_content('honey.json'))
AVATAR_DATA: List[Dict[str, Any]] = json.loads(_get_content('AvatarExcelConfigData.json'))
WEAPON_DATA: List[Dict[str, Any]] = json.loads(_get_content('WeaponExcelConfigData.json'))


def role_to_icon_name(target: int) -> Optional[str]:
    icon_name: Optional[str] = None
    for data in AVATAR_DATA:
        if data['id'] == target:
            icon_name = data['iconName']
    if icon_name is not None:
        return icon_name
    if (role := HONEY_DATA['character'].get(str(target), None)) is not None:
        return "UI_AvatarIcon_" + role[0].title()


def weapon_to_icon_name(target: int) -> Optional[str]:
    icon: Optional[str] = None
    for data in WEAPON_DATA:
        if data['id'] == target:
            icon = data['icon']
    if icon is not None:
        return re.findall(r"UI_EquipIcon_(.*)", icon)[0]
