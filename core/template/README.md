# TemplateService

使用 jinja2 渲染 html 为图片的服务。

## 预览模板

为了方便调试 html，在开发环境中，我们会启动 web server 用于预览模板。（可以在 .env 里调整端口等参数，参数均为 `web_` 开头）

在派蒙收到指令开始渲染某个模板的时候，控制台会输出一个预览链接，类似 `http://localhost:8080/preview/genshin/stats/stats.html?id=45f7d86a-058e-4f64-bdeb-42903d8415b2`，有效时间 8 小时。

如果是无需数据的模板，永久有效，比如 `http://localhost:8080/preview/bot/help/help.html`
