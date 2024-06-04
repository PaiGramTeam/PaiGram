<h1 align="center">PaiGram</h1>

<div align="center"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="">
<img src="https://img.shields.io/badge/works%20on-my%20machine-brightgreen" alt="">
<img src="https://img.shields.io/badge/status-%E5%92%95%E5%92%95%E5%92%95-blue" alt="">
<a href="https://black.readthedocs.io/en/stable/index.html"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="code_style" /></a>
<a href="https://www.codacy.com/gh/PaiGramTeam/PaiGram/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=PaiGramTeam/PaiGram&amp;utm_campaign=Badge_Grade"><img src="https://app.codacy.com/project/badge/Grade/ac5844e2b0d14a3e8aa16b9b1b099ce0" alt=""/></a>
</div>

<p>
<img src="https://user-images.githubusercontent.com/70872201/190447002-119a8819-b111-4a96-a0b3-701c5e256137.png" align="right" width="100px" alt="">
<h2 align="left">简介</h2>

基于 [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 的 PaiGram

![Alt](https://repobeats.axiom.co/api/embed/f73c1121006cb86196f83da2170242b7a97f8be0.svg "Repobeats analytics image")

## 环境需求

- Python 3.11+
- MySQL or SQLite
- Redis

## 使用方法

根据您首选的环境，按照以下设置之一进行操作：

### WSL2 Ubuntu 22.04 设置

对于在 Ubuntu 22.04 上使用 WSL2 的贡献者，请按照[这里的详细指南](/docs/wsl/ZH.md)进行操作。

### 标准设置（所有环境）

#### 1. 从 Git 克隆 PaiGram

```bash
git clone git@github.com:PaiGramTeam/PaiGram.git
cd PaiGram/
git submodule update --init --recursive
```

#### 2. 项目设置

建议使用虚拟环境。您可以通过 `venv` 或 `virtualenv` 进行设置。

**创建虚拟环境：**

```bash
python3 -m venv venv
```

**激活虚拟环境：**

*对于 Linux:*

```bash
source venv/bin/activate
```

*对于 Windows 命令提示符:*

```bash
venv\Scripts\activate.bat
```

*对于 Windows PowerShell:*

```bash
.\venv\Scripts\Activate.ps1
```

**安装依赖：**

```bash
pip install pdm
pdm install
playwright install chromium
```

可选依赖

```bash
pdm install -G :all
```

**编辑配置文件：**

根据给定示例创建 dotenv 配置（`.env`）。确保提供必要的数据库连接详细信息和机器人 token 参数。

```bash
cp .env.example .env
```

要进行详细的配置，请参阅[Wiki/Env 设置](https://github.com/PaiGramTeam/PaiGram/wiki/Env-Settings)。

#### 3. 使用 Alembic 设置数据库

```bash
alembic upgrade head
```

#### 4. 运行 PaiGram

*运行前请确保你依然处于虚拟环境中*

```bash
python ./run.py
```

### 其他部署方法

- **Docker:** 对于使用 Docker
  的部署，请参阅[Wiki/使用 Docker 部署](https://github.com/PaiGramTeam/PaiGram/wiki/Deploy-with-Docker)。

- **Podman:** 对于使用 Podman
  的部署，请参阅[Wiki/使用 Podman 部署](https://github.com/PaiGramTeam/PaiGram/wiki/Deploy-with-Podman)。

## 其他说明

这个项目目前正在扩展，加入更多原神相关娱乐和信息查询功能，敬请期待。

## 感谢

|                                Nickname                                 | Introduce        |
|:-----------------------------------------------------------------------:|------------------|
|          [原神抽卡全机制总结](https://www.bilibili.com/read/cv10468091)          | 本项目抽卡模拟器使用的逻辑    |
| [西风驿站 猫冬](https://bbs.mihoyo.com/ys/accountCenter/postList?id=74019947) | 本项目攻略图图源         |
|           [Yunzai-Bot](https://github.com/Le-niao/Yunzai-Bot)           | 本项使用的抽卡图片和前端资源来源 |
|       [Crawler-ghhw](https://github.com/DGP-Studio/Crawler-ghhw)        | 本项目参考的爬虫代码       |
|                  [Enka.Network](https://enka.network)                   | 角色卡片的数据来源        |
|                    [DGP 胡桃 API](https://hut.ao/zh/)                     | 深渊数据来源           |
