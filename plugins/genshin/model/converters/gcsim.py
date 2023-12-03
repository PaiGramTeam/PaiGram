import re
from collections import Counter
from decimal import Decimal
from functools import lru_cache
from typing import List, Optional, Tuple, Dict

from gcsim_pypi.aliases import CHARACTER_ALIASES, WEAPON_ALIASES, ARTIFACT_ALIASES
from pydantic import ValidationError

from plugins.genshin.model import (
    Set,
    Weapon,
    DigitType,
    WeaponInfo,
    Artifact,
    ArtifactAttributeType,
    Character,
    CharacterInfo,
    GCSim,
    GCSimTarget,
    GCSimWeapon,
    GCSimWeaponInfo,
    GCSimSet,
    GCSimSetInfo,
    GCSimCharacter,
    GCSimEnergySettings,
    GCSimCharacterInfo,
    GCSimCharacterStats,
)
from plugins.genshin.model.metadata import Metadata
from utils.log import logger

metadata = Metadata()


def remove_non_words(text: str) -> str:
    return text.replace("'", "").replace('"', "").replace("-", "").replace(" ", "")


def from_character_gcsim_character(character: Character) -> GCSimCharacter:
    if character == "Raiden Shogun":
        return GCSimCharacter("raiden")
    if character == "Yae Miko":
        return GCSimCharacter("yaemiko")
    if character == "Hu Tao":
        return GCSimCharacter("hutao")
    if character == "Yun Jin":
        return GCSimCharacter("yunjin")
    if character == "Kuki Shinobu":
        return GCSimCharacter("kuki")
    if "Traveler" in character:
        s = character.split(" ")
        traveler_name = "aether" if s[-1] == "Boy" else "lumine"
        return GCSimCharacter(f"{traveler_name}{s[0].lower()}")
    return GCSimCharacter(character.split(" ")[-1].lower())


GCSIM_CHARACTER_TO_CHARACTER: Dict[GCSimCharacter, Tuple[int, Character]] = {}
for char in metadata.characters_metadata.values():
    GCSIM_CHARACTER_TO_CHARACTER[from_character_gcsim_character(char["route"])] = (char["id"], char["route"])
for alias, char in CHARACTER_ALIASES.items():
    if alias not in GCSIM_CHARACTER_TO_CHARACTER:
        if char in GCSIM_CHARACTER_TO_CHARACTER:
            GCSIM_CHARACTER_TO_CHARACTER[alias] = GCSIM_CHARACTER_TO_CHARACTER[char]
        elif alias.startswith("traveler") or alias.startswith("aether") or alias.startswith("lumine"):
            continue
        else:
            logger.warning("Character alias %s not found in GCSIM", alias)

GCSIM_WEAPON_TO_WEAPON: Dict[GCSimWeapon, Tuple[int, Weapon]] = {}
for _weapon in metadata.weapon_metadata.values():
    GCSIM_WEAPON_TO_WEAPON[remove_non_words(_weapon["route"].lower())] = (_weapon["id"], _weapon["route"])
for alias, _weapon in WEAPON_ALIASES.items():
    if alias not in GCSIM_WEAPON_TO_WEAPON:
        if _weapon in GCSIM_WEAPON_TO_WEAPON:
            GCSIM_WEAPON_TO_WEAPON[alias] = GCSIM_WEAPON_TO_WEAPON[_weapon]
        else:
            logger.warning("Weapon alias %s not found in GCSIM", alias)

GCSIM_ARTIFACT_TO_ARTIFACT: Dict[GCSimSet, Tuple[int, Set]] = {}
for _artifact in metadata.artifacts_metadata.values():
    GCSIM_ARTIFACT_TO_ARTIFACT[remove_non_words(_artifact["route"].lower())] = (_artifact["id"], _artifact["route"])
for alias, _artifact in ARTIFACT_ALIASES.items():
    if alias not in GCSIM_ARTIFACT_TO_ARTIFACT:
        if _artifact in GCSIM_ARTIFACT_TO_ARTIFACT:
            GCSIM_ARTIFACT_TO_ARTIFACT[alias] = GCSIM_ARTIFACT_TO_ARTIFACT[_artifact]
        else:
            logger.warning("Artifact alias %s not found in GCSIM", alias)


class GCSimConverter:
    literal_keys_numeric_values_regex = re.compile(
        r"([\w_%]+)=(\d+ *, *\d+ *, *\d+|[\d*\.*\d+]+ *, *[\d*\.*\d+]+|\d+/\d+|\d*\.*\d+|\d+)"
    )

    @classmethod
    def to_character(cls, character: GCSimCharacter) -> Tuple[int, Character]:
        return GCSIM_CHARACTER_TO_CHARACTER[character]

    @classmethod
    def from_character(cls, character: Character) -> GCSimCharacter:
        return from_character_gcsim_character(character)

    @classmethod
    def to_weapon(cls, weapon: GCSimWeapon) -> Tuple[int, Weapon]:
        return GCSIM_WEAPON_TO_WEAPON[weapon]

    @classmethod
    def from_weapon(cls, weapon: Weapon) -> GCSimWeapon:
        return GCSimWeapon(remove_non_words(weapon).lower())

    @classmethod
    def from_weapon_info(cls, weapon_info: Optional[WeaponInfo]) -> GCSimWeaponInfo:
        if weapon_info is None:
            return GCSimWeaponInfo(weapon=GCSimWeapon("dullblade"), refinement=1, level=1, max_level=20)
        return GCSimWeaponInfo(
            weapon=cls.from_weapon(weapon_info.weapon),
            refinement=weapon_info.refinement,
            level=weapon_info.level,
            max_level=weapon_info.max_level,
        )

    @classmethod
    def to_set(cls, set_name: GCSimSet) -> Tuple[int, Set]:
        return GCSIM_ARTIFACT_TO_ARTIFACT[set_name]

    @classmethod
    def from_set(cls, set_name: Set) -> GCSimSet:
        return GCSimSet(remove_non_words(set_name).lower())

    @classmethod
    def from_artifacts(cls, artifacts: List[Artifact]) -> List[GCSimSetInfo]:
        c = Counter()
        for art in artifacts:
            c[cls.from_set(art.set)] += 1
        return [GCSimSetInfo(set=set_name, count=count) for set_name, count in c.items()]

    @classmethod
    @lru_cache
    def from_attribute_type(cls, attribute_type: ArtifactAttributeType) -> str:  # skipcq: PY-R1000
        if attribute_type == ArtifactAttributeType.HP:
            return "HP"
        if attribute_type == ArtifactAttributeType.HP_PERCENT:
            return "HP_PERCENT"
        if attribute_type == ArtifactAttributeType.ATK:
            return "ATK"
        if attribute_type == ArtifactAttributeType.ATK_PERCENT:
            return "ATK_PERCENT"
        if attribute_type == ArtifactAttributeType.DEF:
            return "DEF"
        if attribute_type == ArtifactAttributeType.DEF_PERCENT:
            return "DEF_PERCENT"
        if attribute_type == ArtifactAttributeType.ELEMENTAL_MASTERY:
            return "EM"
        if attribute_type == ArtifactAttributeType.ENERGY_RECHARGE:
            return "ER"
        if attribute_type == ArtifactAttributeType.CRIT_RATE:
            return "CR"
        if attribute_type == ArtifactAttributeType.CRIT_DMG:
            return "CD"
        if attribute_type == ArtifactAttributeType.HEALING_BONUS:
            return "HEAL"
        if attribute_type == ArtifactAttributeType.PYRO_DMG_BONUS:
            return "PYRO_PERCENT"
        if attribute_type == ArtifactAttributeType.HYDRO_DMG_BONUS:
            return "HYDRO_PERCENT"
        if attribute_type == ArtifactAttributeType.DENDRO_DMG_BONUS:
            return "DENDRO_PERCENT"
        if attribute_type == ArtifactAttributeType.ELECTRO_DMG_BONUS:
            return "ELECTRO_PERCENT"
        if attribute_type == ArtifactAttributeType.ANEMO_DMG_BONUS:
            return "ANEMO_PERCENT"
        if attribute_type == ArtifactAttributeType.CRYO_DMG_BONUS:
            return "CRYO_PERCENT"
        if attribute_type == ArtifactAttributeType.GEO_DMG_BONUS:
            return "GEO_PERCENT"
        if attribute_type == ArtifactAttributeType.PHYSICAL_DMG_BONUS:
            return "PHYS_PERCENT"
        raise ValueError(f"Unknown attribute type: {attribute_type}")

    @classmethod
    def from_artifacts_stats(cls, artifacts: List[Artifact]) -> GCSimCharacterStats:
        gcsim_stats = GCSimCharacterStats()
        for art in artifacts:
            main_attr_name = cls.from_attribute_type(art.main_attribute.type)
            setattr(
                gcsim_stats,
                main_attr_name,
                getattr(gcsim_stats, main_attr_name)
                + (
                    Decimal(art.main_attribute.digit.value) / Decimal(100)
                    if art.main_attribute.digit.type == DigitType.PERCENT
                    else Decimal(art.main_attribute.digit.value)
                ),
            )
            for sub_attr in art.sub_attributes:
                attr_name = cls.from_attribute_type(sub_attr.type)
                setattr(
                    gcsim_stats,
                    attr_name,
                    getattr(gcsim_stats, attr_name)
                    + (
                        Decimal(sub_attr.digit.value) / Decimal(100)
                        if sub_attr.digit.type == DigitType.PERCENT
                        else Decimal(sub_attr.digit.value)
                    ),
                )
        return gcsim_stats

    @classmethod
    def from_character_info(cls, character: CharacterInfo) -> GCSimCharacterInfo:
        return GCSimCharacterInfo(
            character=cls.from_character(character.character),
            level=character.level,
            max_level=character.max_level,
            constellation=character.constellation,
            talent=character.skills,
            weapon_info=cls.from_weapon_info(character.weapon_info),
            set_info=cls.from_artifacts(character.artifacts),
            # NOTE: Only stats from arifacts are needed
            stats=cls.from_artifacts_stats(character.artifacts),
        )

    @classmethod
    def merge_character_infos(cls, gcsim: GCSim, character_infos: List[CharacterInfo]) -> GCSim:
        gcsim_characters = {ch.character: ch for ch in gcsim.characters}
        for character_info in character_infos:
            try:
                gcsim_character = cls.from_character_info(character_info)
                if gcsim_character.character in gcsim_characters:
                    gcsim_characters[gcsim_character.character] = gcsim_character
            except ValidationError as e:
                errors = e.errors()
                if errors and errors[0].get("msg").startswith("Not supported"):
                    # Something is not supported, skip
                    continue
                logger.warning("Failed to convert character info: %s", character_info)
        gcsim.characters = list(gcsim_characters.values())
        return gcsim

    @classmethod
    def prepend_scripts(cls, gcsim: GCSim, scripts: List[str]) -> GCSim:
        gcsim.scripts = scripts + gcsim.scripts
        return gcsim

    @classmethod
    def append_scripts(cls, gcsim: GCSim, scripts: List[str]) -> GCSim:
        gcsim.scripts = gcsim.scripts + scripts
        return gcsim

    @classmethod
    def from_gcsim_energy(cls, line: str) -> GCSimEnergySettings:
        energy_settings = GCSimEnergySettings()
        matches = cls.literal_keys_numeric_values_regex.findall(line)
        for key, value in matches:
            if key == "interval":
                energy_settings.intervals = list(map(int, value.split(",")))
            elif key == "amount":
                energy_settings.amount = int(value)
            else:
                logger.warning("Unknown energy setting: %s=%s", key, value)
        return energy_settings

    @classmethod
    def from_gcsim_target(cls, line: str) -> GCSimTarget:
        target = GCSimTarget()
        matches = cls.literal_keys_numeric_values_regex.findall(line)
        for key, value in matches:
            if key == "lvl":
                target.level = int(value)
            elif key == "hp":
                target.hp = int(value)
            elif key == "amount":
                target.amount = int(value)
            elif key == "resist":
                target.resist = float(value)
            elif key == "pos":
                target.position = tuple(p for p in value.split(","))
            elif key == "interval":
                target.interval = list(map(int, value.split(",")))
            elif key == "radius":
                target.radius = float(value)
            elif key == "particle_threshold":
                target.particle_threshold = int(value)
            elif key == "particle_drop_count":
                target.particle_drop_count = int(value)
            elif key in ("pyro", "hydro", "dendro", "electro", "anemo", "cryo", "geo", "physical"):
                target.others[key] = float(value)
            else:
                logger.warning("Unknown target setting: %s=%s", key, value)
        return target

    @classmethod
    def from_gcsim_char_line(cls, line: str, character: GCSimCharacterInfo) -> GCSimCharacterInfo:
        matches = cls.literal_keys_numeric_values_regex.findall(line)
        for key, value in matches:
            if key == "lvl":
                character.level, character.max_level = map(int, value.split("/"))
            elif key == "cons":
                character.constellation = int(value)
            elif key == "talent":
                character.talent = list(map(int, value.split(",")))
            elif key == "start_hp":
                character.start_hp = int(value)
            elif key == "breakthrough":
                character.params.append(f"{key}={value}")
            else:
                logger.warning("Unknown character setting: %s=%s", key, value)
        return character

    @classmethod
    def from_gcsim_weapon_line(cls, line: str, weapon_info: GCSimWeaponInfo) -> GCSimWeaponInfo:
        weapon_name = re.search(r"weapon= *\"(.*)\"", line).group(1)
        if weapon_name not in WEAPON_ALIASES:
            raise ValueError(f"Unknown weapon: {weapon_name}")
        weapon_info.weapon = WEAPON_ALIASES[weapon_name]

        for key, value in cls.literal_keys_numeric_values_regex.findall(line):
            if key == "refine":
                weapon_info.refinement = int(value)
            elif key == "lvl":
                weapon_info.level, weapon_info.max_level = map(int, value.split("/"))
            elif key.startswith("stack"):
                weapon_info.params.append(f"stacks={value}")
            elif key in ("pickup_delay", "breakthrough"):
                weapon_info.params.append(f"{key}={value}")
            else:
                logger.warning("Unknown weapon setting: %s=%s", key, value)
        return weapon_info

    @classmethod
    def from_gcsim_set_line(cls, line: str) -> GCSimSetInfo:
        gcsim_set = re.search(r"set= *\"(.*)\"", line).group(1)
        if gcsim_set not in ARTIFACT_ALIASES:
            raise ValueError(f"Unknown set: {gcsim_set}")
        gcsim_set = ARTIFACT_ALIASES[gcsim_set]
        set_info = GCSimSetInfo(set=gcsim_set)

        for key, value in cls.literal_keys_numeric_values_regex.findall(line):
            if key == "count":
                set_info.count = int(value)
            elif key.startswith("stack"):
                set_info.params.append(f"stacks={value}")
            else:
                logger.warning("Unknown set info: %s=%s", key, value)
        return set_info

    @classmethod
    def from_gcsim_stats_line(cls, line: str, stats: GCSimCharacterStats) -> GCSimCharacterStats:
        matches = re.findall(r"(\w+%?)=(\d*\.*\d+)", line)
        for stat, value in matches:
            attr = stat.replace("%", "_percent").upper()
            setattr(stats, attr, getattr(stats, attr) + Decimal(value))
        return stats

    @classmethod
    def from_gcsim_script(cls, script: str) -> GCSim:  # skipcq: PY-R1000
        options = ""
        characters = {}
        character_aliases = {}
        active_character = None
        targets = []
        energy_settings = GCSimEnergySettings()
        script_lines = []
        for line in script.strip().split("\n"):
            line = line.split("#")[0].strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("options"):
                options = line.strip(";")
            elif line.startswith("target"):
                targets.append(cls.from_gcsim_target(line))
            elif line.startswith("energy"):
                energy_settings = cls.from_gcsim_energy(line)
            elif line.startswith("active"):
                active_character = line.strip(";").split(" ")[1]
            elif m := re.match(r"(\w+) +(char|add weapon|add set|add stats)\W", line):
                if m.group(1) not in CHARACTER_ALIASES:
                    raise ValueError(f"Unknown character: {m.group(1)}")
                c = CHARACTER_ALIASES[m.group(1)]
                if c not in characters:
                    characters[c] = GCSimCharacterInfo(character=c)
                    if m.group(1) != c:
                        character_aliases[m.group(1)] = c
                if m.group(2) == "char":
                    characters[c] = cls.from_gcsim_char_line(line, characters[c])
                elif m.group(2) == "add weapon":
                    characters[c].weapon_info = cls.from_gcsim_weapon_line(line, characters[c].weapon_info)
                elif m.group(2) == "add set":
                    characters[c].set_info.append(cls.from_gcsim_set_line(line))
                elif m.group(2) == "add stats":
                    characters[c].stats = cls.from_gcsim_stats_line(line, characters[c].stats)
            else:
                for key, value in character_aliases.items():
                    line = line.replace(f"{key} ", f"{value} ")
                    line = line.replace(f".{key}.", f".{value}.")
                script_lines.append(line)
        return GCSim(
            options=options,
            characters=list(characters.values()),
            targets=targets,
            energy_settings=energy_settings,
            active_character=active_character,
            script_lines=script_lines,
        )
