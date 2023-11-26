import json
from utils.const import PROJECT_ROOT

METADATA_PATH = PROJECT_ROOT.joinpath("metadata").joinpath("data")
WEAPON_METADATA = {}
ARTIFACTS_METADATA = {}
CHARACTERS_METADATA = {}

def load_metadata():
    global WEAPON_METADATA
    WEAPON_METADATA = json.loads(METADATA_PATH.joinpath("weapon.json").read_text())

    global ARTIFACTS_METADATA
    ARTIFACTS_METADATA = json.loads(METADATA_PATH.joinpath("reliquary.json").read_text())

    global CHARACTERS_METADATA
    CHARACTERS_METADATA = json.loads(METADATA_PATH.joinpath("avatar.json").read_text())
load_metadata()