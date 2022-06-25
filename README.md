<h1 align="center">TGPaimonBot</h1>

<div align="center">
<img src="https://img.shields.io/badge/python-3.8%2B-blue">
<img src="https://img.shields.io/badge/works%20on-my%20machine-brightgreen">
<img src="https://img.shields.io/badge/status-%E5%92%95%E5%92%95%E5%92%95-blue">
</div>


## 简介

基于 
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 
的BOT

## 需求

### 环境需求

- Python 3.8+
- MySQL
- Redis

### 模块需求

因为上游 `genshin.py` 的原因 python 最低版本为 3.8

`python-telegram-bot` 需要预览版本 即 `20.0a0`

出现相关的 `telegram` 模块导入的 `ImportError` 错误需要你手动执行 `pip install python-telegram-bot==20.0a0`

请注意你的 python 是否安装 `aiohttp` （ `genshin.py` 的依赖） 

如果 `aiohttp` 版本大于 `4.0.0a1`
会导致 `redis` 和 `aiohttp` 的依赖 `async-timeout` 版本冲突进而运行代码导致 `TypeError` 异常

解决上面版本冲突导致的错误需要你手动执行 `pip install aiohttp==3.8.1`


### 其他说明

这个项目目前正在扩展，加入更多原神相关娱乐和信息查询功能，敬请期待。

## Thanks
|                       Nickname                        | Introduce         |
|:-----------------------------------------------------:|-------------------|
| [原神抽卡全机制总结](https://www.bilibili.com/read/cv10468091) | 本项目抽卡模拟器使用的逻辑     |
|  [西风驿站](https://bbs.mihoyo.com/ys/collection/307224)  | 本项目攻略图图源          |
|  [Yunzai-Bot](https://github.com/Le-niao/Yunzai-Bot)  | 本项使用的抽卡图片和前端资源来源  |