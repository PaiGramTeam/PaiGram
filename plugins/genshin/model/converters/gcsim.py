from typing import List, Optional
from decimal import Decimal
from functools import lru_cache
from collections import defaultdict, Counter

from plugins.genshin.model import (
    Set,
    Weapon,
    WeaponInfo,
    Artifact,
    ArtifactAttributeType,
    Character,
    CharacterStats,
    CharacterInfo,
    GCSimWeapon,
    GCSimWeaponInfo,
    GCSimSet,
    GCSimSetInfo,
    GCSimCharacter,
    GCSimCharacterInfo,
    GCSimCharacterStats,
)
from plugins.genshin.model.metadata import ARTIFACTS_METADATA, WEAPON_METADATA, CHARACTERS_METADATA


def remove_non_words(text: str) -> str:
    return text.replace("'", "").replace('"', "").replace("-", "").replace(" ", "")


class GCSimReverseConverter:
    @classmethod
    @lru_cache
    def to_char_name(cls, name: str) -> str:
        if name == "Raiden Shogun":
            return "raiden"
        if name == "Yae Miko":
            return "yaemiko"
        if name == "Hu Tao":
            return "hutao"
        if "Traveler" in name:
            s = name.split(" ")
            traveler_name = "aether" if s[-1] == "Boy" else "lumine"
            return f"{traveler_name}{s[0].lower()}"
        return name.split(" ")[-1].lower()

    @classmethod
    def to_char(cls, character: CharacterInfo) -> str:
        return (
            f"{cls.to_char_name(character.character)} "
            "char "
            f"lvl={character.level}/{character.max_level} "
            f"cons={character.constellation} "
            f"talent={','.join(str(skill) for skill in character.skills)};"
        )

    @classmethod
    def to_weapon_name(cls, name: str) -> str:
        return remove_non_words(name).lower()

    @classmethod
    def to_weapon(cls, character: CharacterInfo) -> str:
        if character.weapon_info is None:
            return ""
        return (
            f"{cls.to_char_name(character.character)} "
            f'add weapon="{cls.to_weapon_name(character.weapon_info.weapon)}" '
            f"refine={character.weapon_info.refinement} "
            f"lvl={character.weapon_info.level}/{character.weapon_info.max_level};"
        )

    @classmethod
    @lru_cache
    def to_set_name(cls, name: str) -> str:
        return remove_non_words(name).lower()

    @classmethod
    def to_set(cls, character: CharacterInfo) -> str:
        sets = defaultdict(list)
        for art in character.artifacts:
            sets[art.set].append(art)

        return "\n".join(
            f"{cls.to_char_name(character.character)} "
            f'add set="{cls.to_set_name(set_name)}" '
            f"count={4 if len(artifacts) >= 4 else 2};"
            for set_name, artifacts in sets.items()
            if len(artifacts) >= 2
        )

    @classmethod
    def to_stats(cls, character: CharacterInfo) -> str:
        ret = (
            f"{cls.to_char_name(character.character)} "
            "add stats "
            f"hp={character.stats.HP.value} "
            f"atk={character.stats.ATTACK.value} "
            f"def={character.stats.DEFENSE.value} "
            f"hp%={character.stats.HP_PERCENT.value} "
            f"atk%={character.stats.ATTACK_PERCENT.value} "
            f"def%={character.stats.DEFENSE_PERCENT.value} "
            f"em={character.stats.ELEMENTAL_MASTERY.value} "
            f"er={character.stats.ENERGY_RECHARGE.value} "
            f"cr={character.stats.CRIT_RATE.value} "
            f"cd={character.stats.CRIT_DMG.value} "
        )
        for stat in [
            "PYRO_DMG_BONUS",
            "HYDRO_DMG_BONUS",
            "DENDRO_DMG_BONUS",
            "ELECTRO_DMG_BONUS",
            "CRYO_DMG_BONUS",
            "ANEMO_DMG_BONUS",
            "GEO_DMG_BONUS",
        ]:
            if getattr(character.stats, stat).value > 0:
                ret += f"{stat.split('_')[0].lower()}%={getattr(character.stats, stat).value} "
        if character.stats.PHYSICAL_DMG_BONUS.value > 0:
            ret += f"phys%={character.stats.PHYSICAL_DMG_BONUS.value} "
        if character.stats.HEALING_BONUS.value > 0:
            ret += f"heal={character.stats.HEALING_BONUS.value} "
        return ret.strip() + ";"

    @classmethod
    def to(cls, character: CharacterInfo) -> str:
        lines = []
        lines.append(cls.to_char(character))
        weapon = cls.to_weapon(character)
        if weapon:
            lines.append(weapon)
        lines.append(cls.to_set(character))
        lines.append(cls.to_stats(character))
        return "\n".join(lines)


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
        # TODO: Check whether character is supported
        return remove_non_words(character).lower()

    @classmethod
    def from_weapon(cls, weapon: Weapon) -> GCSimWeapon:
        # TODO: Check whether weapon is supported
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
        # TODO: Check whether set is supported
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
                getattr(gcsim_stats, main_attr_name) + Decimal(art.main_attribute.digit.value),
            )
            for sub_attr in art.sub_attributes:
                attr_name = cls.from_attribute_type(sub_attr.type)
                setattr(gcsim_stats, attr_name, getattr(gcsim_stats, attr_name) + Decimal(sub_attr.digit.value))
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
