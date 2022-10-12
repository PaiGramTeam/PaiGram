from core.base.aiobrowser import AioBrowser
from core.service import init_service
from core.base.redisdb import RedisDB
from core.template.services import TemplateService
from core.template.cache import TemplatePreviewCache

@init_service
def create_template_service(browser: AioBrowser, redis: RedisDB):
    _cache = TemplatePreviewCache(redis)
    _service = TemplateService(browser, _cache)
    return _service
