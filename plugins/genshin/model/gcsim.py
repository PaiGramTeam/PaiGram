from typing import Any, NewType, List, Optional, Tuple, Dict
from decimal import Decimal
from pydantic import BaseModel, validator

from gcsim_pypi.availability import AVAILABLE_ARTIFACTS, AVAILABLE_CHARACTERS, AVAILABLE_WEAPONS
from gcsim_pypi.aliases import ARTIFACT_ALIASES, CHARACTER_ALIASES, WEAPON_ALIASES


GCSimCharacter = NewType("GCSimCharacter", str)
GCSimWeapon = NewType("GCSimWeapon", str)
GCSimSet = NewType("GCSimSet", str)


class GCSimWeaponInfo(BaseModel):
    weapon: GCSimWeapon = "dullblade"
    refinement: int = 1
    level: int = 1
    max_level: int = 20
    params: List[str] = []

    @validator("weapon")
    def validate_weapon(cls, v):
        if v not in AVAILABLE_WEAPONS or v not in WEAPON_ALIASES:
            raise ValueError(f"Not supported weapon: {v}")
        return WEAPON_ALIASES[v]


class GCSimSetInfo(BaseModel):
    set: GCSimSet
    count: int = 2
    params: List[str] = []

    @validator("set")
    def validate_set(cls, v):
        if v not in AVAILABLE_ARTIFACTS or v not in ARTIFACT_ALIASES:
            raise ValueError(f"Not supported set: {v}")
        return ARTIFACT_ALIASES[v]


class GCSimCharacterStats(BaseModel):
    HP: Decimal = Decimal(0)
    HP_PERCENT: Decimal = Decimal(0)
    ATK: Decimal = Decimal(0)
    ATK_PERCENT: Decimal = Decimal(0)
    DEF: Decimal = Decimal(0)
    DEF_PERCENT: Decimal = Decimal(0)
    EM: Decimal = Decimal(0)
    ER: Decimal = Decimal(0)
    CR: Decimal = Decimal(0)
    CD: Decimal = Decimal(0)
    HEAL: Decimal = Decimal(0)
    PYRO_PERCENT: Decimal = Decimal(0)
    HYDRO_PERCENT: Decimal = Decimal(0)
    DENDRO_PERCENT: Decimal = Decimal(0)
    ELECTRO_PERCENT: Decimal = Decimal(0)
    ANEMO_PERCENT: Decimal = Decimal(0)
    CRYO_PERCENT: Decimal = Decimal(0)
    GEO_PERCENT: Decimal = Decimal(0)
    PHYS_PERCENT: Decimal = Decimal(0)


class GCSimCharacterInfo(BaseModel):
    character: GCSimCharacter
    level: int = 1
    max_level: int = 20
    constellation: int = 0
    talent: List[int] = [1, 1, 1]
    start_hp: Optional[int] = None
    weapon_info: GCSimWeaponInfo = GCSimWeaponInfo()
    set_info: List[GCSimSetInfo] = []
    stats: GCSimCharacterStats = GCSimCharacterStats()
    params: List[str] = []

    @validator("character")
    def validate_character(cls, v):
        if v not in AVAILABLE_CHARACTERS or v not in CHARACTER_ALIASES:
            raise ValueError(f"Not supported character: {v}")
        return CHARACTER_ALIASES[v]

    @property
    def char(self) -> str:
        return self.character

    @property
    def char_line(self) -> str:
        return (
            " ".join(
                filter(
                    lambda w: w,
                    [
                        f"{self.char}",
                        "char",
                        f"lvl={self.level}/{self.max_level}",
                        f"cons={self.constellation}",
                        f"start_hp={self.start_hp}" if self.start_hp is not None else "",
                        f"talent={','.join(str(t) for t in self.talent)}",
                        f"+params=[{','.join(self.params)}] " if self.params else "",
                    ],
                )
            )
            + ";"
        )

    @property
    def weapon_line(self) -> str:
        return (
            " ".join(
                filter(
                    lambda w: w,
                    [
                        f"{self.char}",
                        f'add weapon="{self.weapon_info.weapon}"',
                        f"refine={self.weapon_info.refinement}",
                        f"lvl={self.weapon_info.level}/{self.weapon_info.max_level}",
                        f"+params=[{','.join(self.weapon_info.params)}] " if self.weapon_info.params else "",
                    ],
                )
            )
            + ";"
        )

    @property
    def set_line(self) -> str:
        return "\n".join(
            " ".join(
                filter(
                    lambda w: w,
                    [
                        f"{self.char}",
                        f'add set="{set_info.set}"',
                        f"count={4 if set_info.count >= 4 else 2}",
                        f"+params=[{','.join(set_info.params)}] " if set_info.params else "",
                    ],
                )
            )
            + ";"
            for set_info in self.set_info
            # NOTE: 祭*系列似乎并不支持
            if set_info.count > 1
        )

    @property
    def stats_line(self) -> str:
        if all(value == 0 for _, value in self.stats):
            return ""
        return (
            f"{self.char} add stats "
            + " ".join(
                [
                    f"{stat.replace('_PERCENT', '%').lower()}={value:.4f}"
                    if stat.endswith("_PERCENT") or stat in {"CR", "CD", "ER"}
                    else f"{stat.lower()}={value:.2f}"
                    for stat, value in iter(self.stats)
                    if value > 0
                ]
            )
            + ";"
        )

    def __str__(self) -> str:
        return "\n".join([self.char_line, self.weapon_line, self.set_line, self.stats_line])


class GCSimTarget(BaseModel):
    level: int = 100
    resist: float = 0.1
    position: Tuple[str, str] = ("0", "0")
    interval: List[int] = []
    radius: Optional[float] = None
    hp: Optional[int] = None
    amount: Optional[int] = None
    particle_threshold: Optional[int] = None
    particle_drop_count: Optional[int] = None
    others: Dict[str, Any] = {}

    def __str__(self) -> str:
        return (
            " ".join(
                filter(
                    lambda w: w,
                    [
                        f"target lvl={self.level} resist={self.resist} ",
                        f"pos={','.join(self.position)}",
                        f"radius={self.radius}" if self.radius is not None else "",
                        f"hp={self.hp}" if self.hp is not None else "",
                        f"amount={self.amount}" if self.amount is not None else "",
                        f"interval={','.join(str(i) for i in self.interval)}" if self.interval else "",
                        f"particle_threshold={self.particle_threshold}" if self.particle_threshold is not None else "",
                        f"particle_drop_count={self.particle_drop_count}"
                        if self.particle_drop_count is not None
                        else "",
                        " ".join([f"{k}={v}" for k, v in self.others.items()]),
                    ],
                )
            )
            + ";"
        )


class GCSimEnergySettings(BaseModel):
    intervals: List[int] = [480, 720]
    amount: int = 1

    def __str__(self) -> str:
        return f"energy every interval={','.join(str(i) for i in self.intervals)} amount={self.amount};"


class GCSim(BaseModel):
    options: Optional[str] = None
    characters: List[GCSimCharacterInfo] = []
    targets: List[GCSimTarget] = [GCSimTarget()]
    energy_settings: Optional[GCSimEnergySettings] = None
    # TODO: Do we even want this?
    hurt_settings: Optional[str] = None
    active_character: Optional[GCSimCharacter] = None
    script_lines: List[str] = []

    def __str__(self) -> str:
        line = ""
        if self.options:
            line += f"{self.options};\n"
        line += "\n".join([str(c) for c in self.characters])
        line += "\n"
        line += "\n".join([str(t) for t in self.targets])
        line += "\n"
        if self.energy_settings:
            line += f"{self.energy_settings}\n"
        if self.active_character:
            line += f"active {self.active_character};\n"
        else:
            line += f"active {self.characters[0].char};\n"
        line += "\n".join(self.script_lines)
        line += "\n"
        return line
