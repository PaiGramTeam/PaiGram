from core.base.aiobrowser import AioBrowser
from core.service import init_service
from core.base.redisdb import RedisDB
from core.template.services import TemplateService
from core.template.cache import TemplatePreviewCache, HtmlToFileIdCache


@init_service
def create_template_service(browser: AioBrowser, redis: RedisDB):
    _preview_cache = TemplatePreviewCache(redis)
    _html_to_file_id_cache = HtmlToFileIdCache(redis)
    _service = TemplateService(browser, _html_to_file_id_cache, _preview_cache)
    return _service
