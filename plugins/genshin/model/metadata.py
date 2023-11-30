from typing import Dict, Any

from utils.const import PROJECT_ROOT

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

METADATA_PATH = PROJECT_ROOT.joinpath("metadata").joinpath("data")


class Metadata:
    _instance: "Metadata" = None
    weapon_metadata: Dict[str, Any] = {}
    artifacts_metadata: Dict[str, Any] = {}
    characters_metadata: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.reload_assets()
        return cls._instance

    def reload_assets(self) -> None:
        self.__load_assets_data()

    def __load_assets_data(self) -> None:
        self.weapon_metadata = jsonlib.loads(METADATA_PATH.joinpath("weapon.json").read_text())
        self.artifacts_metadata = jsonlib.loads(METADATA_PATH.joinpath("reliquary.json").read_text())
        self.characters_metadata = jsonlib.loads(METADATA_PATH.joinpath("avatar.json").read_text())
