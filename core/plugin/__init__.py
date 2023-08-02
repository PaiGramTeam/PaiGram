"""插件"""

from gram_core.plugin._handler import conversation, error_handler, handler
from gram_core.plugin._job import TimeType, job
from gram_core.plugin._plugin import Plugin, PluginType, get_all_plugins

__all__ = (
    "Plugin",
    "PluginType",
    "get_all_plugins",
    "handler",
    "error_handler",
    "conversation",
    "job",
    "TimeType",
)
