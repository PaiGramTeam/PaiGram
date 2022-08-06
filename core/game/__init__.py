from utils.redisdb import RedisDB
from utils.service.manager import listener_service
from .cache import GameStrategyCache
from .services import GameStrategyService


@listener_service()
def create_game_strategy_service(redis: RedisDB):
    _cache = GameStrategyCache(redis)
    _service = GameStrategyService(_cache)
    return _service
