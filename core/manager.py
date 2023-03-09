import asyncio
from importlib import import_module
from pathlib import Path
from typing import Dict, Generic, List, Optional, TYPE_CHECKING, Type, TypeVar

from arkowrapper import ArkoWrapper
from async_timeout import timeout
from typing_extensions import ParamSpec

from core.base_service import BaseServiceType, ComponentType, DependenceType, get_all_services
from core.config import config as bot_config
from utils.const import PLUGIN_DIR, PROJECT_ROOT
from utils.helpers import gen_pkg
from utils.log import logger

if TYPE_CHECKING:
    from core.application import Application
    from core.plugin import PluginType
    from core.builtins.executor import Executor

__all__ = ("DependenceManager", "PluginManager", "ComponentManager", "ServiceManager", "Managers")

R = TypeVar("R")
T = TypeVar("T")
P = ParamSpec("P")


def _load_module(path: Path) -> None:
    for pkg in gen_pkg(path):
        try:
            logger.debug('正在导入 "%s"', pkg)
            import_module(pkg)
        except Exception as e:
            logger.exception(
                '在导入 "%s" 的过程中遇到了错误 [red bold]%s[/]', pkg, type(e).__name__, exc_info=e, extra={"markup": True}
            )
            raise SystemExit from e


class Manager(Generic[T]):
    """生命周期控制基类"""

    _executor: Optional["Executor"] = None
    _lib: Dict[Type[T], T] = {}
    _application: "Optional[Application]" = None

    def set_application(self, application: "Application") -> None:
        self._application = application

    @property
    def application(self) -> "Application":
        if self._application is None:
            raise RuntimeError(f"No application was set for this {self.__class__.__name__}.")
        return self._application

    @property
    def executor(self) -> "Executor":
        """执行器"""
        if self._executor is None:
            raise RuntimeError(f"No executor was set for this {self.__class__.__name__}.")
        return self._executor

    def build_executor(self, name: str):
        from core.builtins.executor import Executor
        from core.builtins.dispatcher import BaseDispatcher

        self._executor = Executor(name, dispatcher=BaseDispatcher)
        self._executor.set_application(self.application)


class DependenceManager(Manager[DependenceType]):
    """基础依赖管理"""

    _dependency: Dict[Type[DependenceType], DependenceType] = {}

    @property
    def dependency(self) -> List[DependenceType]:
        return list(self._dependency.values())

    @property
    def dependency_map(self) -> Dict[Type[DependenceType], DependenceType]:
        return self._dependency

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
        async def task(d):
            try:
                async with timeout(5):
                    await d.shutdown()
                    logger.debug('基础服务 "%s" 关闭成功', d.__class__.__name__)
            except asyncio.TimeoutError:
                logger.warning('基础服务 "%s" 关闭超时', d.__class__.__name__)
            except Exception as e:
                logger.error('基础服务 "%s" 关闭错误', d.__class__.__name__, exc_info=e)

        tasks = []
        for dependence in self._dependency.values():
            tasks.append(asyncio.create_task(task(dependence)))

        await asyncio.gather(*tasks)


class ComponentManager(Manager[ComponentType]):
    """组件管理"""

    _components: Dict[Type[ComponentType], ComponentType] = {}

    @property
    def components(self) -> List[ComponentType]:
        return list(self._components.values())

    @property
    def components_map(self) -> Dict[Type[ComponentType], ComponentType]:
        return self._components

    async def init_components(self):
        for path in filter(
            lambda x: x.is_dir() and not x.name.startswith("_"), PROJECT_ROOT.joinpath("core/services").iterdir()
        ):
            _load_module(path)
        components = ArkoWrapper(get_all_services()).filter(lambda x: x.is_component)
        retry_times = 0
        max_retry_times = len(components)
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
                except Exception as e:  # pylint: disable=W0703
                    logger.debug('组件 "%s" 初始化失败: [red]%s[/]', component.__name__, e, extra={"markup": True})
            end_len = len(list(components))
            if start_len == end_len:
                retry_times += 1

            if retry_times == max_retry_times and components:
                for component in components:
                    logger.error('组件 "%s" 初始化失败', component.__name__)
                raise SystemExit


class ServiceManager(Manager[BaseServiceType]):
    """服务控制类"""

    _services: Dict[Type[BaseServiceType], BaseServiceType] = {}

    @property
    def services(self) -> List[BaseServiceType]:
        return list(self._services.values())

    @property
    def services_map(self) -> Dict[Type[BaseServiceType], BaseServiceType]:
        return self._services

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

        except Exception as e:  # pylint: disable=W0703
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

        async def task(s):
            try:
                async with timeout(5):
                    await s.shutdown()
                    logger.success('服务 "%s" 关闭成功', s.__class__.__name__)
            except asyncio.TimeoutError:
                logger.warning('服务 "%s" 关闭超时', s.__class__.__name__)
            except Exception as e:
                logger.warning('服务 "%s" 关闭失败', s.__class__.__name__, exc_info=e)

        logger.info("正在关闭服务")
        tasks = []
        for service in self._services.values():
            tasks.append(asyncio.create_task(task(service)))

        await asyncio.gather(*tasks)


class PluginManager(Manager["PluginType"]):
    """插件管理"""

    _plugins: Dict[Type["PluginType"], "PluginType"] = {}

    @property
    def plugins(self) -> List["PluginType"]:
        """所有已经加载的插件"""
        return list(self._plugins.values())

    @property
    def plugins_map(self) -> Dict[Type["PluginType"], "PluginType"]:
        return self._plugins

    async def install_plugins(self) -> None:
        """安装所有插件"""
        from core.plugin import get_all_plugins

        for path in filter(lambda x: x.is_dir(), PLUGIN_DIR.iterdir()):
            _load_module(path)

        for plugin in get_all_plugins():
            plugin: Type["PluginType"]

            try:
                instance: "PluginType" = await self.executor(plugin)
            except Exception as e:  # pylint: disable=W0703
                logger.error('插件 "%s" 初始化失败', f"{plugin.__module__}.{plugin.__name__}", exc_info=e)
                continue

            self._plugins[plugin] = instance

            if self._application is not None:
                instance.set_application(self._application)

            await asyncio.create_task(self.plugin_install_task(plugin, instance))

    @staticmethod
    async def plugin_install_task(plugin: Type["PluginType"], instance: "PluginType"):
        try:
            await instance.install()
            logger.success('插件 "%s" 安装成功', f"{plugin.__module__}.{plugin.__name__}")
        except Exception as e:  # pylint: disable=W0703
            logger.error('插件 "%s" 安装失败', f"{plugin.__module__}.{plugin.__name__}", exc_info=e)

    async def uninstall_plugins(self) -> None:
        for plugin in self._plugins.values():
            try:
                await plugin.uninstall()
            except Exception as e:  # pylint: disable=W0703
                logger.error('插件 "%s" 卸载失败', f"{plugin.__module__}.{plugin.__name__}", exc_info=e)


class Managers(DependenceManager, ComponentManager, ServiceManager, PluginManager):
    """BOT 除自身外的生命周期管理类"""
