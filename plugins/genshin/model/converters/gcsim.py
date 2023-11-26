import re
from typing import List, Optional
from decimal import Decimal
from functools import lru_cache
from collections import defaultdict, Counter

from utils.log import logger

from plugins.genshin.model import (
    Set,
    Weapon,
    DigitType,
    WeaponInfo,
    Artifact,
    ArtifactAttributeType,
    Character,
    CharacterStats,
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
from plugins.genshin.model.metadata import ARTIFACTS_METADATA, WEAPON_METADATA, CHARACTERS_METADATA


def remove_non_words(text: str) -> str:
    return text.replace("'", "").replace('"', "").replace("-", "").replace(" ", "")


class GCSimConverter:
    @classmethod
    def from_character(cls, character: Character) -> GCSimCharacter:
        if character == "Raiden Shogun":
            return "raiden"
        if character == "Yae Miko":
            return "yaemiko"
        if character == "Hu Tao":
            return "hutao"
        if "Traveler" in character:
            s = character.split(" ")
            traveler_name = "aether" if s[-1] == "Boy" else "lumine"
            return f"{traveler_name}{s[0].lower()}"
        return character.split(" ")[-1].lower()

    @classmethod
    def from_weapon(cls, weapon: Weapon) -> GCSimWeapon:
        return remove_non_words(weapon).lower()

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
    def from_set(cls, set_name: Set) -> GCSimSet:
        return remove_non_words(set_name).lower()

    @classmethod
    def from_artifacts(cls, artifacts: List[Artifact]) -> List[GCSimSetInfo]:
        c = Counter()
        for art in artifacts:
            c[cls.from_set(art.set)] += 1
        return [GCSimSetInfo(set=set_name, count=count) for set_name, count in c.items()]

    @classmethod
    @lru_cache
    def from_attribute_type(cls, attribute_type: ArtifactAttributeType) -> str:
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
    def from_gcsim_energy(cls, line: str) -> GCSimEnergySettings:
        energy_settings = GCSimEnergySettings()
        for word in line.strip(";").split(" every ")[-1].split(" "):
            if word.startswith("interval="):
                energy_settings.intervals = list(map(int, word.split("=")[-1].split(",")))
            elif word.startswith("amount="):
                energy_settings.amount = int(word.split("=")[-1])
            else:
                logger.warning(f"Unknown energy setting: {word}")
        return energy_settings

    @classmethod
    def from_gcsim_target(cls, line: str) -> GCSimTarget:
        target = GCSimTarget()
        for word in line.strip(";")[7:].split(" "):
            if word.startswith("lvl="):
                target.level = int(word.split("=")[-1])
            elif word.startswith("resist="):
                target.resist = float(word.split("=")[-1])
            elif word.startswith("pos="):
                target.position = tuple(p for p in word.split("=")[-1].split(","))
            elif word.startswith("radius="):
                target.radius = float(word.split("=")[-1])
            elif word.startswith("hp="):
                target.hp = int(word.split("=")[-1])
            elif word.startswith("particle_threshold="):
                target.particle_threshold = int(word.split("=")[-1])
            elif word.startswith("particle_drop_count="):
                target.particle_drop_count = int(word.split("=")[-1])
            else:
                logger.warning(f"Unknown target setting: {word}")
        return target

    @classmethod
    def from_gcsim_char_line(cls, line: str, character: GCSimCharacterInfo) -> GCSimCharacterInfo:
        for word in line.strip(";").split(" char ")[-1].split(" "):
            if word.startswith("lvl="):
                character.level, character.max_level = map(int, word.split("=")[-1].split("/"))
            elif word.startswith("cons="):
                character.constellation = int(word.split("=")[-1])
            elif word.startswith("talent="):
                character.talent = [int(t) for t in word.split("=")[-1].split(",")]
            else:
                logger.warning(f"Unknown character setting: {word}")
        return character

    @classmethod
    def from_gcsim_weapon_line(cls, line: str, weapon_info: GCSimWeaponInfo) -> GCSimWeaponInfo:
        for word in line.strip(";").split(" add ")[-1].split(" "):
            if word.startswith("lvl="):
                weapon_info.level, weapon_info.max_level = map(int, word.split("=")[-1].split("/"))
            elif word.startswith("refine="):
                weapon_info.refinement = int(word.split("=")[-1])
            elif word.startswith("weapon="):
                weapon_info.weapon = word.split("=")[-1].strip('"')
            else:
                logger.warning(f"Unknown weapon info: {word}")
        return weapon_info

    @classmethod
    def from_gcsim_set_line(cls, line: str) -> GCSimSetInfo:
        gcsim_set = None
        count = 0
        for word in line.strip(";").split(" add ")[-1].split(" "):
            if word.startswith("set="):
                gcsim_set = word.split("=")[-1].strip('"')
            elif word.startswith("count="):
                count = int(word.split("=")[-1])
            else:
                logger.warning(f"Unknown set info: {word}")
        return GCSimSetInfo.construct(set=gcsim_set, count=count)

    @classmethod
    def from_gcsim_stats_line(cls, line: str, stats: GCSimCharacterStats) -> GCSimCharacterStats:
        matches = re.findall(r"(\w+[%]{0,1})=(\d*\.*\d+)", line)
        for stat, value in matches:
            attr = stat.replace("%", "_percent").upper()
            setattr(stats, attr, getattr(stats, attr) + Decimal(value))
        return stats

    @classmethod
    def from_gcsim_script(cls, script: str) -> GCSim:
        options = ""
        characters = {}
        active_character = None
        targets = []
        energy_settings = GCSimEnergySettings()
        loop = 0
        script_lines = []
        script_for_loop_started = False
        brackets = []
        unparsed_lines = []
        for line in script.strip().split("\n"):
            line = line.strip()
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
            elif m := re.match(r"(\w+) (char|add weapon|add set|add stats)", line):
                if m.group(1) not in characters:
                    characters[m.group(1)] = GCSimCharacterInfo(character=m.group(1))
                if m.group(2) == "char":
                    characters[m.group(1)] = cls.from_gcsim_char_line(line, characters[m.group(1)])
                elif m.group(2) == "add weapon":
                    characters[m.group(1)].weapon_info = cls.from_gcsim_weapon_line(
                        line, characters[m.group(1)].weapon_info
                    )
                elif m.group(2) == "add set":
                    characters[m.group(1)].set_info.append(cls.from_gcsim_set_line(line))
                elif m.group(2) == "add stats":
                    characters[m.group(1)].stats = cls.from_gcsim_stats_line(line, characters[m.group(1)].stats)
            elif line.startswith("while"):
                script_for_loop_started = True
                if line.endswith("{"):
                    brackets.append("{")
            elif line.startswith("for"):
                script_for_loop_started = True
                if m := re.search(r"\w+[ ]*<(=){0,1}[ ]*(\d+)", line):
                    loop = int(m.group(2)) + (1 if m.group(1) else 0)
                if line.endswith("{"):
                    brackets.append("{")
            elif line.endswith("{"):
                brackets.append("{")
            elif line.endswith("}"):
                if brackets[-1] == "{":
                    brackets.pop()
                    if not brackets:
                        script_for_loop_started = False
                else:
                    raise ValueError(f"Unmatched bracket in line: {line}\nscript:\n{script}")
            elif script_for_loop_started:
                script_lines.append(line)
            else:
                unparsed_lines.append(line)
        return GCSim(
            options=options,
            characters=list(characters.values()),
            targets=targets,
            energy_settings=energy_settings,
            active_character=active_character,
            loop=loop,
            unparsed=unparsed_lines,
            script="\n".join(script_lines) if script_lines else "\n".join(unparsed_lines),
        )
