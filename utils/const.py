"""常量"""
from pathlib import Path

__all__ = [
    'PROJECT_ROOT', 'PLUGIN_DIR', 'SERVICE_DIR',
]

PROJECT_ROOT = Path(__file__).joinpath('../..').resolve()
PLUGIN_DIR = PROJECT_ROOT / 'plugins'
SERVICE_DIR = PROJECT_ROOT / 'service'
