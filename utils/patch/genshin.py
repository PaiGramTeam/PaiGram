import typing

from genshin import types, utility
import genshin.client.components.calculator  # pylint: disable=W0406
import genshin.models.genshin as genshin_models  # pylint: disable=W0406

from utils.patch.methods import patch, patchable


@patch(genshin.client.components.calculator.CalculatorClient)
class CalculatorClient:
    @patchable
    async def get_character_details(
        self,
        character: types.IDOr[genshin_models.Character],
        *,
        uid: typing.Optional[int] = None,
        lang: typing.Optional[str] = None,
    ):
        uid = uid or await self._get_uid(types.Game.GENSHIN)

        data = await self.request_calculator(
            "sync/avatar/detail",
            method="GET",
            lang=lang,
            params=dict(
                avatar_id=int(character),
                uid=uid,
                region=utility.recognize_genshin_server(uid),
            ),
        )
        if data.get("weapon") is None:
            weapon = {
                "id": character.weapon.id,
                "name": character.weapon.name,
                "icon": character.weapon.icon,
                "weapon_cat_id": character.weapon.type,
                "weapon_level": character.weapon.rarity,
                "max_level": 90,
                "level_current": character.weapon.level,
            }
            data["weapon"] = weapon
        return genshin_models.CalculatorCharacterDetails(**data)
