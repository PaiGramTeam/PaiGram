"""此模块包含BOT Utils的错误的基类"""


class NotFoundError(Exception):
    entity_name: str
    entity_value_name: str = "value"

    def __init__(self, entity_value):
        super().__init__(f"{self.entity_name} not found, {self.entity_value_name}: {entity_value}")


class RegionNotFoundError(NotFoundError):
    entity_name: str = "RegionEnum"
    entity_value_name: str = "region"


class UrlResourcesNotFoundError(NotFoundError):
    entity_name: str = "url resources"
    entity_value_name: str = "url"
