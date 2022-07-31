from app.game.cache import GameStrategyCache
from app.game.service import GameStrategyService
from utils.app.manager import listener_service
from utils.redisdb import RedisDB


@listener_service()
def create_game_strategy_service(redis: RedisDB):
    _cache = GameStrategyCache(redis)
    _service = GameStrategyService(_cache)
    return _service
