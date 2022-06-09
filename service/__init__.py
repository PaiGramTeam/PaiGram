from service.admin import AdminService
from service.cache import RedisCache
from service.gacha import GachaService
from service.game import GetGameInfo
from service.quiz import QuizService
from service.repository import AsyncRepository
from service.template import TemplateService
from service.user import UserInfoFormDB
from utils.aiobrowser import AioBrowser
from utils.mysql import MySQL
from utils.redisdb import RedisDB


class BaseService:
    def __init__(self, mysql: MySQL, redis: RedisDB, browser: AioBrowser):
        self.repository = AsyncRepository(mysql)
        self.cache = RedisCache(redis)
        self.user_service_db = UserInfoFormDB(self.repository)
        self.quiz_service = QuizService(self.repository, self.cache)
        self.get_game_info = GetGameInfo(self.repository, self.cache)
        self.gacha = GachaService(self.repository, self.cache)
        self.admin = AdminService(self.repository, self.cache)
        self.template = TemplateService(browser)


class StartService(BaseService):
    pass
