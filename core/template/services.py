import time
from typing import Optional
from urllib.parse import urlencode, urljoin, urlsplit

from jinja2 import Environment, FileSystemLoader, Template
from playwright.async_api import ViewportSize
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2.exceptions import TemplateNotFound

from core.base.aiobrowser import AioBrowser
from core.bot import bot
from core.base.webserver import webapp
from utils.const import PROJECT_ROOT
from utils.log import logger
from core.template.cache import TemplatePreviewCache


class _QuerySelectorNotFound(Exception):
    pass


class TemplateService:
    def __init__(self, browser: AioBrowser, preview_cache: TemplatePreviewCache, template_dir: str = "resources"):
        self._browser = browser
        self.template_dir = PROJECT_ROOT / template_dir

        self._jinja2_env = Environment(
            loader=FileSystemLoader(template_dir),
            enable_async=True,
            autoescape=True,
            auto_reload=bot.config.debug,
        )

        self.previewer = TemplatePreviewer(self, preview_cache)

    def get_template(self, template_name: str) -> Template:
        return self._jinja2_env.get_template(template_name)

    async def render_async(self, template_name: str, template_data: dict):
        """模板渲染
        :param template_name: 模板文件名
        :param template_data: 模板数据
        """
        start_time = time.time()
        template = self.get_template(template_name)
        html = await template.render_async(**template_data)
        logger.debug(f"{template_name} 模板渲染使用了 {str(time.time() - start_time)}")
        return html

    async def render(
        self,
        template_name: str,
        template_data: dict,
        viewport: ViewportSize = None,
        full_page: bool = True,
        evaluate: Optional[str] = None,
        query_selector: str = None,
    ) -> bytes:
        """模板渲染成图片
        :param template_path: 模板目录
        :param template_name: 模板文件名
        :param template_data: 模板数据
        :param viewport: 截图大小
        :param full_page: 是否长截图
        :param evaluate: 页面加载后运行的 js
        :param query_selector: 截图选择器
        :return:
        """
        start_time = time.time()
        template = self.get_template(template_name)
        html = await template.render_async(**template_data)
        logger.debug(f"{template_name} 模板渲染使用了 {str(time.time() - start_time)}")

        if bot.config.debug:
            preview_url = await self.previewer.get_preview_url(template_name, template_data)
            logger.debug(f"调试模板 URL: {preview_url}")

        browser = await self._browser.get_browser()
        start_time = time.time()
        page = await browser.new_page(viewport=viewport)
        uri = (PROJECT_ROOT / template.filename).as_uri()
        await page.goto(uri)
        await page.set_content(html, wait_until="networkidle")
        if evaluate:
            await page.evaluate(evaluate)
        clip = None
        if query_selector:
            try:
                card = await page.query_selector(query_selector)
                if not card:
                    raise _QuerySelectorNotFound
                clip = await card.bounding_box()
                if not clip:
                    raise _QuerySelectorNotFound
            except _QuerySelectorNotFound:
                logger.warning(f"未找到 {query_selector} 元素")
        png_data = await page.screenshot(clip=clip, full_page=full_page)
        await page.close()
        logger.debug(f"{template_name} 图片渲染使用了 {str(time.time() - start_time)}")
        return png_data


class TemplatePreviewer:
    def __init__(self, template_service: TemplateService, cache: TemplatePreviewCache):
        self.template_service = template_service
        self.cache = cache
        self.register_routes()

    async def get_preview_url(self, template: str, data: dict):
        """获取预览 URL"""
        components = urlsplit(bot.config.web_url)
        path = urljoin("/preview/", template)
        query = {}

        # 如果有数据，暂存在 redis 中
        if data:
            key = str(uuid4())
            await self.cache.set_data(key, data)
            query["key"] = key

        return components._replace(path=path, query=urlencode(query)).geturl()

    def register_routes(self):
        """注册预览用到的路由"""

        @webapp.get("/preview/{path:path}")
        async def preview_template(path: str, key: Optional[str] = None): # pylint: disable=W0612
            # 如果是 /preview/ 开头的静态文件，直接返回内容。比如使用相对链接 ../ 引入的静态资源
            if not path.endswith(".html"):
                full_path = self.template_service.template_dir / path
                if not full_path.is_file():
                    raise HTTPException(status_code=404, detail=f"Template '{path}' not found")
                return FileResponse(full_path)

            # 取回暂存的渲染数据
            data = await self.cache.get_data(key) if key else {}
            if key and data is None:
                raise HTTPException(status_code=404, detail=f"Template data {key} not found")

            # 渲染 jinja2 模板
            try:
                html = await self.template_service.render_async(path, data)
                # 将本地 URL file:// 修改为 HTTP url，因为浏览器内不允许加载本地文件
                # file:///project_dir/cache/image.jpg => /cache/image.jpg
                html = html.replace(PROJECT_ROOT.as_uri(), "")
                return HTMLResponse(html)
            except TemplateNotFound as e:
                logger.error(e)
                raise HTTPException(status_code=404, detail=f"Template '{path}' not found")

        # 其他静态资源
        for name in ["cache", "resources"]:
            webapp.mount(f"/{name}", StaticFiles(directory=PROJECT_ROOT / name), name=name)
