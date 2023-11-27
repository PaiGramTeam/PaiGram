from decimal import Decimal
from enkanetwork import (
    CharacterInfo as EnkaCharacterInfo,
    CharacterStats as EnkaCharacterStats,
    StatsPercentage,
    Equipments,
    EquipmentsType,
    EquipType,
    EquipmentsStats,
    DigitType as EnkaDigitType,
)

from plugins.genshin.model import (
    CharacterInfo,
    Digit,
    DigitType,
    CharacterStats,
    WeaponInfo,
    WeaponType,
    Artifact,
    ArtifactPosition,
    ArtifactAttribute,
    ArtifactAttributeType,
)
from plugins.genshin.model.metadata import ARTIFACTS_METADATA, WEAPON_METADATA, CHARACTERS_METADATA


class EnkaConverter:
    @classmethod
    def to_weapon_type(cls, type_str: str) -> WeaponType:
        if type_str == "WEAPON_BOW":
            return WeaponType.BOW
        if type_str == "WEAPON_CATALYST":
            return WeaponType.CATALYST
        if type_str == "WEAPON_CLAYMORE":
            return WeaponType.CLAYMORE
        if type_str == "WEAPON_POLE":
            return WeaponType.POLEARM
        if type_str == "WEAPON_SWORD_ONE_HAND":
            return WeaponType.SWORD
        if type_str == "单手剑":
            return WeaponType.SWORD
        raise ValueError(f"Unknown weapon type: {type_str}")

    @classmethod
    def to_weapon_info(cls, equipment: Equipments) -> WeaponInfo:
        if equipment.type != EquipmentsType.WEAPON:
            raise ValueError(f"Not weapon equipment type: {equipment.type}")

        weapon_data = WEAPON_METADATA.get(str(equipment.id))
        if not weapon_data:
            raise ValueError(f"Unknown weapon id: {equipment.id}")

        return WeaponInfo(
            id=equipment.id,
            weapon=weapon_data["route"],
            type=cls.to_weapon_type(weapon_data["type"]),
            level=equipment.level,
            max_level=equipment.max_level,
            refinement=equipment.refinement,
            ascension=equipment.ascension,
        )

    @classmethod
    def to_artifact_attribute_type(cls, prop_id: str) -> ArtifactAttributeType:
        if prop_id == "FIGHT_PROP_HP":
            return ArtifactAttributeType.HP
        if prop_id == "FIGHT_PROP_ATTACK":
            return ArtifactAttributeType.ATK
        if prop_id == "FIGHT_PROP_DEFENSE":
            return ArtifactAttributeType.DEF
        if prop_id == "FIGHT_PROP_HP_PERCENT":
            return ArtifactAttributeType.HP_PERCENT
        if prop_id == "FIGHT_PROP_ATTACK_PERCENT":
            return ArtifactAttributeType.ATK_PERCENT
        if prop_id == "FIGHT_PROP_DEFENSE_PERCENT":
            return ArtifactAttributeType.DEF_PERCENT
        if prop_id == "FIGHT_PROP_ELEMENT_MASTERY":
            return ArtifactAttributeType.ELEMENTAL_MASTERY
        if prop_id == "FIGHT_PROP_CHARGE_EFFICIENCY":
            return ArtifactAttributeType.ENERGY_RECHARGE
        if prop_id == "FIGHT_PROP_CRITICAL":
            return ArtifactAttributeType.CRIT_RATE
        if prop_id == "FIGHT_PROP_CRITICAL_HURT":
            return ArtifactAttributeType.CRIT_DMG
        if prop_id == "FIGHT_PROP_HEAL_ADD":
            return ArtifactAttributeType.HEALING_BONUS
        if prop_id == "FIGHT_PROP_FIRE_ADD_HURT":
            return ArtifactAttributeType.PYRO_DMG_BONUS
        if prop_id == "FIGHT_PROP_WATER_ADD_HURT":
            return ArtifactAttributeType.HYDRO_DMG_BONUS
        if prop_id == "FIGHT_PROP_ELEC_ADD_HURT":
            return ArtifactAttributeType.ELECTRO_DMG_BONUS
        if prop_id == "FIGHT_PROP_ICE_ADD_HURT":
            return ArtifactAttributeType.CRYO_DMG_BONUS
        if prop_id == "FIGHT_PROP_WIND_ADD_HURT":
            return ArtifactAttributeType.ANEMO_DMG_BONUS
        if prop_id == "FIGHT_PROP_ROCK_ADD_HURT":
            return ArtifactAttributeType.GEO_DMG_BONUS
        if prop_id == "FIGHT_PROP_GRASS_ADD_HURT":
            return ArtifactAttributeType.DENDRO_DMG_BONUS
        if prop_id == "FIGHT_PROP_PHYSICAL_ADD_HURT":
            return ArtifactAttributeType.PHYSICAL_DMG_BONUS
        raise ValueError(f"Unknown artifact attribute type: {prop_id}")

    @classmethod
    def to_artifact_attribute(cls, equip_stat: EquipmentsStats) -> ArtifactAttribute:
        return ArtifactAttribute(
            type=cls.to_artifact_attribute_type(equip_stat.prop_id),
            digit=Digit(
                value=Decimal(equip_stat.value),
                type=DigitType.PERCENT if equip_stat.type == EnkaDigitType.PERCENT else DigitType.NUMERIC,
            ),
        )

    @classmethod
    def to_artifact_position(cls, equip_type: EquipType) -> ArtifactPosition:
        if equip_type == EquipType.Flower:
            return ArtifactPosition.FLOWER
        if equip_type == EquipType.Feather:
            return ArtifactPosition.PLUME
        if equip_type == EquipType.Sands:
            return ArtifactPosition.SANDS
        if equip_type == EquipType.Goblet:
            return ArtifactPosition.GOBLET
        if equip_type == EquipType.Circlet:
            return ArtifactPosition.CIRCLET
        raise ValueError(f"Unknown artifact position: {equip_type}")

    @classmethod
    def to_artifact(cls, equipment: Equipments) -> Artifact:
        if equipment.type != EquipmentsType.ARTIFACT:
            raise ValueError(f"Not artifact equipment type: {equipment.type}")

        artifact_data = next(
            (data for data in ARTIFACTS_METADATA.values() if data["name"] == equipment.detail.artifact_name_set), None
        )
        if not artifact_data:
            raise ValueError(f"Unknown artifact: {equipment}")

        return Artifact(
            id=artifact_data["id"],
            set=artifact_data["route"],
            position=cls.to_artifact_position(equipment.detail.artifact_type),
            level=equipment.level,
            rarity=equipment.detail.rarity,
            main_attribute=cls.to_artifact_attribute(equipment.detail.mainstats),
            sub_attributes=[cls.to_artifact_attribute(stat) for stat in equipment.detail.substats],
        )

    @classmethod
    def to_character_stats(cls, character_stats: EnkaCharacterStats) -> CharacterStats:
        return CharacterStats(
            **{
                stat: Digit(
                    value=Decimal(value.value),
                    type=DigitType.PERCENT if isinstance(value, StatsPercentage) else DigitType.NUMERIC,
                )
                for stat, value in character_stats._iter()
            }
        )

    @classmethod
    def to_character(cls, character_info: EnkaCharacterInfo) -> str:
        character_id = str(character_info.id)
        if character_id == "10000005" or character_id == "10000007":
            character_id += f"-{character_info.element.name.lower()}"
        character_data = CHARACTERS_METADATA.get(character_id)
        if not character_data:
            raise ValueError(f"Unknown character: {character_info.name}\n{character_info}")
        return character_data["route"]

    @classmethod
    def to_character_info(cls, character_info: EnkaCharacterInfo) -> CharacterInfo:
        weapon_equip = next((equip for equip in character_info.equipments if equip.type == EquipmentsType.WEAPON), None)
        artifacts_equip = [equip for equip in character_info.equipments if equip.type == EquipmentsType.ARTIFACT]
        return CharacterInfo(
            id=character_info.id,
            character=cls.to_character(character_info),
            rarity=character_info.rarity,
            weapon_info=cls.to_weapon_info(weapon_equip) if weapon_equip else None,
            artifacts=[cls.to_artifact(equip) for equip in artifacts_equip],
            level=character_info.level,
            max_level=character_info.max_level,
            ascension=character_info.ascension,
            constellation=character_info.constellations_unlocked,
            skills=[skill.level for skill in character_info.skills],
            stats=cls.to_character_stats(character_info.stats),
        )
