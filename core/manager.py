from arkowrapper import ArkoWrapper
from asyncio import CancelledError
from importlib import import_module
from pathlib import Path
from typing import Dict, Generic, List, Optional, TYPE_CHECKING, Type, TypeVar

from async_timeout import timeout
from typing_extensions import ParamSpec

from core.base_service import BaseServiceType, ComponentType, DependenceType, get_all_services
from core.config import config as bot_config
from core.plugin import PluginType, get_all_plugins
from utils.const import PLUGIN_DIR, PROJECT_ROOT
from utils.helpers import gen_pkg
from utils.log import logger

if TYPE_CHECKING:
    from core.builtins.executor import BaseExecutor

R = TypeVar("R")
T = TypeVar("T")
P = ParamSpec("P")


def _load_module(path: Path) -> None:
    for pkg in gen_pkg(path):
        try:
            import_module(pkg)
        except Exception as e:
            logger.exception(
                '在导入文件 "%s" 的过程中遇到了错误 [red bold]%s[/]', pkg, type(e).__name__, exc_info=e, extra={"markup": True}
            )
            raise SystemExit from e


class Manager(Generic[T]):
    """生命周期控制基类"""

    _executor: Optional["BaseExecutor"] = None
    _lib: Dict[Type[T], T] = {}

    @property
    def executor(self) -> "BaseExecutor":
        """执行器"""
        from core.builtins.executor import BaseExecutor

        if self._executor is None:
            self._executor = BaseExecutor("Bot")

        return self._executor


class DependenceManager(Manager[DependenceType]):
    """基础依赖管理"""

    _dependency: Dict[Type[DependenceType], DependenceType] = {}

    @property
    def dependency(self) -> List[DependenceType]:
        return list(self._dependency.values())

    async def start_dependency(self) -> None:
        _load_module(PROJECT_ROOT / "core/dependence")

        for dependence in filter(lambda x: x.is_dependence, get_all_services()):
            dependence: Type[DependenceType]
            instance: DependenceType
            try:
                if hasattr(dependence, "from_config"):  # 如果有 from_config 方法
                    instance = dependence.from_config(bot_config)  # 用 from_config 实例化服务
                else:
                    instance = await self.executor(dependence)

                await instance.initialize()
                logger.success('基础服务 "%s" 启动成功', dependence.__name__)

                self._lib[dependence] = instance
                self._dependency[dependence] = instance

            except Exception as e:
                logger.exception('基础服务 "%s" 初始化失败，BOT 将自动关闭', dependence.__name__)
                raise SystemExit from e

    async def stop_dependency(self) -> None:
        for dependence in self._dependency.values():
            await dependence.shutdown()


class ComponentManager(Manager[ComponentType]):
    """组件管理"""

    _components: Dict[Type[ComponentType], ComponentType] = {}

    @property
    def components(self) -> List[ComponentType]:
        return list(self._components.values())

    async def init_components(self):
        for path in filter(
            lambda x: x.is_dir() and not x.name.startswith("_"), PROJECT_ROOT.joinpath("core/services").iterdir()
        ):
            _load_module(path)
        components = ArkoWrapper(get_all_services()).filter(lambda x: x.is_component)
        retry_times = 0
        while components:
            start_len = len(components)
            for component in list(components):
                component: Type[ComponentType]
                instance: ComponentType
                try:
                    instance = await self.executor(component)
                    self._lib[component] = instance
                    self._components[component] = instance
                    components = components.remove(component)
                except Exception as e:
                    logger.debug(f'组件 "{component.__name__}" 初始化失败: [red]{e}[/]', extra={"markup": True})
            end_len = len(components)
            if start_len == end_len:
                retry_times += 1

            if retry_times > 2:
                for component in components:
                    logger.error('组件 "%s" 初始化失败', component.__name__)
                raise SystemExit


class ServiceManager(Manager[BaseServiceType]):
    """服务控制类"""

    _services: Dict[Type[BaseServiceType], BaseServiceType] = {}

    @property
    def services(self) -> List[BaseServiceType]:
        return list(self._services.values())

    async def _initialize_service(self, target: Type[BaseServiceType]) -> BaseServiceType:
        instance: BaseServiceType
        try:
            if hasattr(target, "from_config"):  # 如果有 from_config 方法
                instance = target.from_config(bot_config)  # 用 from_config 实例化服务
            else:
                instance = await self.executor(target)

            await instance.initialize()
            logger.success('服务 "%s" 启动成功', target.__name__)

            return instance

        except Exception as e:
            logger.exception('服务 "%s" 初始化失败，BOT 将自动关闭', target.__name__)
            raise SystemExit from e

    async def start_services(self) -> None:
        for path in filter(
            lambda x: x.is_dir() and not x.name.startswith("_"), PROJECT_ROOT.joinpath("core/services").iterdir()
        ):
            _load_module(path)

        for service in filter(lambda x: not x.is_component and not x.is_dependence, get_all_services()):  # 遍历所有服务类
            instance = await self._initialize_service(service)

            self._lib[service] = instance
            self._services[service] = instance

    async def stop_services(self) -> None:
        """关闭服务"""
        if not self._services:
            return
        logger.info("正在关闭服务")
        for service in self._services.values():
            async with timeout(5):
                try:
                    await service.shutdown()
                    logger.success('服务 "%s" 关闭成功', service.__class__.__name__)
                except CancelledError:
                    logger.warning('服务 "%s" 关闭超时', service.__class__.__name__)
                except Exception as e:  # pylint: disable=W0703
                    logger.exception('服务 "%s" 关闭失败', service.__class__.__name__, exc_info=e)


class PluginManager(Manager[PluginType]):
    """插件管理"""

    _plugins: List[PluginType] = []

    @property
    def plugins(self) -> List[PluginType]:
        """所有已经加载的插件"""
        return self._plugins

    async def install_plugins(self) -> None:
        for path in filter(lambda x: x.is_dir(), PLUGIN_DIR.iterdir()):
            _load_module(path)
        for plugin in get_all_plugins():
            try:
                instance: PluginType = await self.executor(plugin)
            except Exception as e:
                logger.exception('插件 "%s" 初始化失败', f"{plugin.__module__}.{plugin.__name__}", exc_info=e)
                continue
            self._plugins.append(instance)

            try:
                await plugin.install()
            except Exception as e:
                logger.exception('插件 "%s" 安装失败', f"{plugin.__module__}.{plugin.__name__}", exc_info=e)
                continue

    async def uninstall_plugins(self) -> None:
        for plugin in self._plugins:
            try:
                await plugin.uninstall()
            except Exception as e:
                logger.exception('插件 "%s" 卸载失败', f"{plugin.__module__}.{plugin.__name__}", exc_info=e)
