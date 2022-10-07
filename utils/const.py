"""常量"""
from pathlib import Path

from httpx import URL

__all__ = [
    'PROJECT_ROOT', 'PLUGIN_DIR', 'RESOURCE_DIR',
    'NOT_SET',
    'HONEY_HOST', 'ENKA_HOST', 'AMBR_HOST', 'CELESTIA_HOST',
]

# 项目根目录
PROJECT_ROOT = Path(__file__).joinpath('../..').resolve()
# Core 目录
CORE_DIR = PROJECT_ROOT / 'core'
# 插件目录
PLUGIN_DIR = PROJECT_ROOT / 'plugins'
# 资源目录
RESOURCE_DIR = PROJECT_ROOT / 'resources'

NOT_SET = object()

HONEY_HOST = URL("https://genshin.honeyhunterworld.com/")
ENKA_HOST = URL("https://enka.network/")
AMBR_HOST = URL("https://api.ambr.top/")
CELESTIA_HOST = URL("https://www.projectcelestia.com/")
