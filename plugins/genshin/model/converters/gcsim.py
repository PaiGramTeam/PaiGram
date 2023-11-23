from collections import defaultdict
from functools import lru_cache
from ..model import Character, CharacterStats

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
    def to_char(cls, character: Character) -> str:
        return (
            f"{cls.to_char_name(character.name)} "
            "char "
            f"lvl={character.level}/{character.max_level} "
            f"cons={character.constellation} "
            f"talent={','.join(str(skill) for skill in character.skills)};"
        )
    
    @classmethod
    def to_weapon_name(cls, name: str) -> str:
        return name.replace("'", "").replace('"', "").replace("-", "").replace(" ", "").lower()

    @classmethod
    def to_weapon(cls, character: Character) -> str:
        if character.weapon is None:
            return ""
        return (
            f"{cls.to_char_name(character.name)} "
            f'add weapon="{cls.to_weapon_name(character.weapon.name)}" '
            f"refine={character.weapon.refinement} "
            f"lvl={character.weapon.level}/{character.weapon.max_level};"
        )

    @classmethod
    @lru_cache
    def to_set_name(cls, name: str) -> str:
        return name.replace("'", "").replace('"', "").replace("-", "").replace(" ", "").lower()

    @classmethod
    def to_set(cls, character: Character) -> str:
        sets = defaultdict(list)
        for art in character.artifacts:
            sets[art.name].append(art)
        
        return '\n'.join(
            f"{cls.to_char_name(character.name)} "
            f'add set="{cls.to_set_name(name)}" '
            f"count={4 if len(artifacts) >= 4 else 2};"
            for name, artifacts in sets.items() if len(artifacts) >= 2
        )

    @classmethod
    def to_stats(cls, character: Character) -> str:
        ret = (
            f"{cls.to_char_name(character.name)} "
            "add stats "
            f"hp={character.stats.HP} "
            f"atk={character.stats.ATTACK} "
            f"def={character.stats.DEFENSE} "
            f"hp%={character.stats.HP_PERCENT} "
            f"atk%={character.stats.ATTACK_PERCENT} "
            f"def%={character.stats.DEFENSE_PERCENT} "
            f"em={character.stats.ELEMENTAL_MASTERY} "
            f"er={character.stats.ENERGY_RECHARGE} "
            f"cr={character.stats.CRIT_RATE} "
            f"cd={character.stats.CRIT_DMG} "
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
            if getattr(character.stats, stat) > 0:
                ret += f"{stat.split('_')[0].lower()}%={getattr(character.stats, stat)} "
        if character.stats.PHYSICAL_DMG_BONUS > 0:
            ret += f"phys%={character.stats.PHYSICAL_DMG_BONUS} "
        if character.stats.HEALING_BONUS > 0:
            ret += f"heal={character.stats.HEALING_BONUS} "
        return ret.strip() + ";"
    
    @classmethod
    def to(cls, character: Character) -> str:
        lines = []
        lines.append(cls.to_char(character))
        weapon = cls.to_weapon(character)
        if weapon:
            lines.append(weapon)
        lines.append(cls.to_set(character))
        lines.append(cls.to_stats(character))
        return '\n'.join(lines)
