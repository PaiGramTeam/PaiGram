import os
from glob import glob
from importlib import import_module
from os import path
from typing import List, Union

from logger import Log
from models.base import ModuleInfo


class ModulesManager:
    def __init__(self):
        self.manager_name: str = "模块管理器"
        self.modules_list: List[ModuleInfo] = []  # 用于存储文件名称
        self.exclude_list: List[str] = []

    def clear(self):
        self.modules_list.clear()

    def refresh_list(self, pathname: str):
        path_list = [i.replace(os.sep, "/") for i in glob(pathname)]
        for temp_path in path_list:
            if "__" in temp_path:
                continue
            if os.path.isdir(temp_path):
                self.modules_list.append(ModuleInfo(relative_path=temp_path))
            else:
                module_name = path.basename(path.normpath(temp_path))
                root, ext = os.path.splitext(module_name)
                if ext == ".py":
                    self.modules_list.append(ModuleInfo(relative_path=temp_path))

    def add_exclude(self, exclude: Union[str, List[str]]):
        if isinstance(exclude, str):
            self.exclude_list.append(exclude)
        elif isinstance(exclude, list):
            self.exclude_list.extend(exclude)
        else:
            raise TypeError

    def import_module(self):
        module_name_list: List[str] = []
        for module_info in self.modules_list:
            if module_info.module_name not in self.exclude_list:
                try:
                    import_module(f"{module_info.package_path}")
                except ImportError as exc:
                    Log.warning(f"{self.manager_name}加载 {module_info} 失败", exc)
                except ImportWarning as exc:
                    Log.warning(f"{self.manager_name}加载 {module_info} 成功但有警告", exc)
                except BaseException as exc:
                    Log.warning(f"{self.manager_name}加载 {module_info} 失败", exc)
                else:
                    module_name_list.append(module_info.module_name)
        Log.info(f"{self.manager_name}加载模块: " + ", ".join(module_name_list))
