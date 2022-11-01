from pathlib import Path

__all__ = ['PROJECT_ROOT', 'CORE_DIR', 'PLUGIN_DIR', 'RESOURCE_DIR']

# 项目根目录
PROJECT_ROOT = Path(__file__).joinpath("../../..").resolve()
# Core 目录
CORE_DIR = PROJECT_ROOT / "core"
# 插件目录
PLUGIN_DIR = PROJECT_ROOT / "plugins"
# 资源目录
RESOURCE_DIR = PROJECT_ROOT / "resources"
