from app.template.service import TemplateService
from utils.aiobrowser import AioBrowser
from utils.app.manager import listener_service


@listener_service()
def create_template_service(browser: AioBrowser):
    _service = TemplateService(browser)
    return _service
