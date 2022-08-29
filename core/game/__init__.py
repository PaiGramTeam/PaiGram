from utils.redisdb import RedisDB
from utils.service.manager import listener_service
from .cache import GameCache
from .services import GameStrategyService, GameMaterialService


@listener_service()
def create_game_strategy_service(redis: RedisDB):
    _cache = GameCache(redis, "game:strategy")
    return GameStrategyService(_cache)


@listener_service()
def create_game_material_service(redis: RedisDB):
    _cache = GameCache(redis, "game:material")
    return GameMaterialService(_cache)
