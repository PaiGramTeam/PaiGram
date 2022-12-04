from core.service import init_service
from .services import SearchServices as _SearchServices

__all__ = []


@init_service
def create_search_service():
    _service = _SearchServices()
    return _service
