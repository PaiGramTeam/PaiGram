from service.admin import AdminService
from service.gacha import GachaService
from service.game import GetGameInfo
from service.quiz import QuizService
from service.repository import AsyncRepository
from service.cache import RedisCache
from service.template import TemplateService
from service.user import UserInfoFormDB


class BaseService:
    def __init__(self, async_repository: AsyncRepository, async_cache: RedisCache):
        self.repository = async_repository
        self.cache = async_cache
        self.user_service_db = UserInfoFormDB(self.repository)
        self.quiz_service = QuizService(self.repository, self.cache)
        self.get_game_info = GetGameInfo(self.repository, self.cache)
        self.gacha = GachaService(self.repository, self.cache)
        self.admin = AdminService(self.repository, self.cache)
        self.template = TemplateService()


class StartService(BaseService):
    def __init__(self, async_repository: AsyncRepository, async_cache: RedisCache):
        super().__init__(async_repository, async_cache)
