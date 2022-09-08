"""常量"""
from pathlib import Path

__all__ = [
    'PROJECT_ROOT', 'PLUGIN_DIR',
    'NOT_SET',
]

# 项目根目录
PROJECT_ROOT = Path(__file__).joinpath('../..').resolve()
# 插件目录
PLUGIN_DIR = PROJECT_ROOT / 'plugins'

NOT_SET = object()
