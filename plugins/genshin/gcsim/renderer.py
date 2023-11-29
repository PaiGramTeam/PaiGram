import json
from pathlib import Path
from typing import Optional

from metadata.shortname import idToName, elementToName, elementsToColor
from core.dependence.assets import AssetsService
from gram_core.services.template.models import RenderResult
from gram_core.services.template.services import TemplateService
from plugins.genshin.model import CharacterInfo
from plugins.genshin.model.converters.gcsim import GCSimConverter


class GCSimResultRenderer:
    def __init__(self, assets_service: AssetsService, template_service: TemplateService):
        self.assets_service = assets_service
        self.template_service = template_service

    async def prepare_result(self, result_path: Path, character_infos: list[CharacterInfo]) -> Optional[dict]:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["extra"] = {}
        for idx, character_details in enumerate(result["character_details"]):
            asset_id, character = GCSimConverter.to_character(character_details["name"])
            character_info: CharacterInfo = next(filter(lambda c: c.character == character, character_infos), None)
            if not character_info:
                return None
            if character_details["name"] not in result["extra"]:
                result["extra"][character_details["name"]] = {}

            result["extra"][character_details["name"]]["icon"] = (
                await self.assets_service.avatar(asset_id).icon()
            ).as_uri()
            result["extra"][character_details["name"]]["rarity"] = character_info.rarity
            result["extra"][character_details["name"]]["constellation"] = character_info.constellation

            if "character_dps" not in result["extra"]:
                result["extra"]["character_dps"] = []
            result["extra"]["character_dps"].append(
                {"value": result["statistics"]["character_dps"][idx]["mean"], "name": idToName(character_info.id)}
            )
        result["extra"]["element_dps"] = [
            {"value": data["mean"], "name": elementToName(elem), "itemStyle": {"color": elementsToColor[elem]}}
            for elem, data in result["statistics"]["element_dps"].items()
        ]
        result["extra"]["damage"] = {
            "xAxis": [i * 0.5 for i in range(len(result["statistics"]["damage_buckets"]["buckets"]))],
            "series": [
                {
                    "data": [bucket["mean"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                    "type": "line",
                    "stack": "x",
                    "areaStyle": {},
                    "name": "平均伤害",
                },
                {
                    "data": [bucket["min"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                    "type": "line",
                    "stack": "x",
                    "name": "最小伤害",
                },
                {
                    "data": [bucket["max"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                    "type": "line",
                    "stack": "x",
                    "name": "最大伤害",
                },
                {
                    "data": [bucket["sd"] for bucket in result["statistics"]["damage_buckets"]["buckets"]],
                    "type": "line",
                    "stack": "x",
                    "name": "标准差",
                },
            ],
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
