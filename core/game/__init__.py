from core.base.redisdb import RedisDB
from core.service import init_service

from .cache import GameCache
from .services import GameMaterialService, GameStrategyService


@init_service
def create_game_strategy_service(redis: RedisDB):
    _cache = GameCache(redis, "game:strategy")
    return GameStrategyService(_cache)


@init_service
def create_game_material_service(redis: RedisDB):
    _cache = GameCache(redis, "game:material")
    return GameMaterialService(_cache)
