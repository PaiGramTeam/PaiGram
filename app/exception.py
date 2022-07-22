class NotFoundError(Exception):
    entity_name: str
    entity_value_name: str = "value"

    def __init__(self, entity_value):
        super().__init__(f"{self.entity_name} not found, {self.entity_value_name}: {entity_value}")
