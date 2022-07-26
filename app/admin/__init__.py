from app.admin.cache import BotAdminCache
from app.admin.repositories import BotAdminRepository
from app.admin.service import BotAdminService
from utils.app.manager import listener_service
from utils.mysql import MySQL
from utils.redisdb import RedisDB


@listener_service()
def create_bot_admin_service(mysql: MySQL, redis: RedisDB):
    _cache = BotAdminCache(redis)
    _repository = BotAdminRepository(mysql)
    _service = BotAdminService(_repository, _cache)
    return _service
