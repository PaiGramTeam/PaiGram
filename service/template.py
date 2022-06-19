import os
import time
from typing import Optional

from jinja2 import PackageLoader, Environment, Template
from playwright.async_api import ViewportSize

from config import config
from logger import Log
from utils.aiobrowser import AioBrowser


class TemplateService:
    def __init__(self, browser: AioBrowser, template_package_name: str = "resources", cache_dir_name: str = "cache"):
        self.browser = browser
        self._template_package_name = template_package_name
        self._current_dir = os.getcwd()
        self._output_dir = os.path.join(self._current_dir, cache_dir_name)
        if not os.path.exists(self._output_dir):
            os.mkdir(self._output_dir)
        self._jinja2_env = {}
        self._jinja2_template = {}

    def get_template(self, package_path: str, template_name: str, auto_escape: bool = True) -> Template:
        if config.DEBUG:
            # DEBUG下 禁止复用 方便查看和修改模板
            loader = PackageLoader(self._template_package_name, package_path)
            jinja2_env = Environment(loader=loader, enable_async=True, autoescape=auto_escape)
            jinja2_template = jinja2_env.get_template(template_name)
        else:
            jinja2_env: Environment = self._jinja2_env.get(package_path)
            jinja2_template: Template = self._jinja2_template.get(package_path + template_name)
            if jinja2_env is None:
                loader = PackageLoader(self._template_package_name, package_path)
                jinja2_env = Environment(loader=loader, enable_async=True, autoescape=auto_escape)
                jinja2_template = jinja2_env.get_template(template_name)
                self._jinja2_env[package_path] = jinja2_env
                self._jinja2_template[package_path + template_name] = jinja2_template
        return jinja2_template

    async def render(self, template_path: str, template_name: str, template_data: dict,
                     viewport: ViewportSize, full_page: bool = True, auto_escape: bool = True,
                     evaluate: Optional[str] = None) -> bytes:
        """
        模板渲染成图片
        :param template_path: 模板目录
        :param template_name: 模板文件名
        :param template_data: 模板数据
        :param viewport: 截图大小
        :param full_page: 是否长截图
        :param auto_escape: 是否自动转义
        :param evaluate: 页面加载后运行的 js
        :return:
        """
        start_time = time.time()
        template = self.get_template(template_path, template_name, auto_escape)
        template_data["res_path"] = f"file://{self._current_dir}"
        html = await template.render_async(**template_data)
        Log.debug(f"{template_name} 模板渲染使用了 {str(time.time() - start_time)}")
        browser = await self.browser.get_browser()
        start_time = time.time()
        page = await browser.new_page(viewport=viewport)
        await page.goto(f"file://{template.filename}")
        await page.set_content(html, wait_until="networkidle")
        if evaluate:
            await page.evaluate(evaluate)
        png_data = await page.screenshot(full_page=full_page)
        await page.close()
        Log.debug(f"{template_name} 图片渲染使用了 {str(time.time() - start_time)}")
        return png_data
