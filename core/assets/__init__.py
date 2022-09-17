from core.service import init_service
from .service import AssetsService


@init_service
def create_wiki_service():
    _service = AssetsService()
    return _service
