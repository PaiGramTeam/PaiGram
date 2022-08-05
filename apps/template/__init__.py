from utils.aiobrowser import AioBrowser
from utils.apps.manager import listener_service
from .services import TemplateService


@listener_service()
def create_template_service(browser: AioBrowser):
    _service = TemplateService(browser)
    return _service
