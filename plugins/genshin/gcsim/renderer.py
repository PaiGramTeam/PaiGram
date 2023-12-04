import json
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from core.dependence.assets import AssetsService
from gram_core.services.template.models import RenderResult
from gram_core.services.template.services import TemplateService
from metadata.shortname import idToName, elementToName, elementsToColor
from plugins.genshin.model import GCSim, GCSimCharacterInfo, CharacterInfo
from plugins.genshin.model.converters.gcsim import GCSimConverter

if TYPE_CHECKING:
    from utils.typedefs import StrOrInt


class GCSimResultRenderer:
    def __init__(self, assets_service: AssetsService, template_service: TemplateService):
        self.assets_service = assets_service
        self.template_service = template_service

    @staticmethod
    def fix_asset_id(asset_id: "StrOrInt") -> "StrOrInt":
        if "-" in str(asset_id):
            _asset_id = asset_id.split("-")[0]
            if _asset_id.isnumeric():
                return int(_asset_id)
        return asset_id

    async def prepare_result(
        self, result_path: Path, script: GCSim, character_infos: List[CharacterInfo]
    ) -> Optional[dict]:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        characters = {ch.character for ch in character_infos}
        result["extra"] = {}
        for idx, character_details in enumerate(result["character_details"]):
            asset_id, _ = GCSimConverter.to_character(character_details["name"])
            asset_id = self.fix_asset_id(asset_id)
            gcsim_character: GCSimCharacterInfo = next(
                filter(lambda gc, cn=character_details["name"]: gc.character == cn, script.characters), None
            )
            if not gcsim_character:
                return None
            if character_details["name"] not in result["extra"]:
                result["extra"][character_details["name"]] = {}
            if GCSimConverter.to_character(gcsim_character.character)[1] in characters:
                result["extra"][character_details["name"]]["owned"] = True
            else:
                result["extra"][character_details["name"]]["owned"] = False

            result["extra"][character_details["name"]]["icon"] = (
                await self.assets_service.avatar(asset_id).icon()
            ).as_uri()
            result["extra"][character_details["name"]]["rarity"] = self.assets_service.avatar(asset_id).enka.rarity
            result["extra"][character_details["name"]]["constellation"] = gcsim_character.constellation

            if "character_dps" not in result["extra"]:
                result["extra"]["character_dps"] = []
            result["extra"]["character_dps"].append(
                {"value": result["statistics"]["character_dps"][idx]["mean"], "name": idToName(asset_id)}
            )
        result["extra"]["element_dps"] = [
            {"value": data["mean"], "name": elementToName(elem), "itemStyle": {"color": elementsToColor[elem]}}
            for elem, data in result["statistics"]["element_dps"].items()
        ]
        result["extra"]["damage"] = {
            "xAxis": [i * 0.5 for i in range(len(result["statistics"]["damage_buckets"]["buckets"]))],
            "data": {
                "mean": [bucket["mean"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                "min": [bucket["min"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                "max": [bucket["max"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                "sd": [bucket["sd"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
            },
        }

        return result

    async def render(self, script_key: str, data: dict) -> RenderResult:
        return await self.template_service.render(
            "genshin/gcsim/result.jinja2",
            {"script_key": script_key, **data},
            full_page=True,
            query_selector="body > div",
            ttl=7 * 24 * 60 * 60,
        )
