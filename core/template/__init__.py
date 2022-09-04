from core.base.aiobrowser import AioBrowser
from core.service import init_service
from .services import TemplateService


@init_service
def create_template_service(browser: AioBrowser):
    _service = TemplateService(browser)
    return _service
