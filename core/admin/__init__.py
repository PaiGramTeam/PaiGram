from core.admin.cache import BotAdminCache
from core.admin.repositories import BotAdminRepository
from core.admin.services import BotAdminService
from core.base.mysql import MySQL
from core.base.redisdb import RedisDB
from core.service import init_service


@init_service
def create_bot_admin_service(mysql: MySQL, redis: RedisDB):
    _cache = BotAdminCache(redis)
    _repository = BotAdminRepository(mysql)
    _service = BotAdminService(_repository, _cache)
    return _service
