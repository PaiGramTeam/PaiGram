from utils.apps.manager import listener_service
from utils.mysql import MySQL
from utils.redisdb import RedisDB
from .cache import BotAdminCache
from .repositories import BotAdminRepository
from .services import BotAdminService


@listener_service()
def create_bot_admin_service(mysql: MySQL, redis: RedisDB):
    _cache = BotAdminCache(redis)
    _repository = BotAdminRepository(mysql)
    _service = BotAdminService(_repository, _cache)
    return _service
