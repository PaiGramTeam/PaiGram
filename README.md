<h1 align="center">PaiGram</h1>

<div align="center"><img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="">
<img src="https://img.shields.io/badge/works%20on-my%20machine-brightgreen" alt="">
<img src="https://img.shields.io/badge/status-%E5%92%95%E5%92%95%E5%92%95-blue" alt="">
<a href="https://black.readthedocs.io/en/stable/index.html"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="code_style" /></a>
<a href="https://www.codacy.com/gh/PaiGramTeam/PaiGram/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=PaiGramTeam/PaiGram&amp;utm_campaign=Badge_Grade"><img src="https://app.codacy.com/project/badge/Grade/ac5844e2b0d14a3e8aa16b9b1b099ce0" alt=""/></a>
</div>

<p>
<img src="https://user-images.githubusercontent.com/70872201/190447002-119a8819-b111-4a96-a0b3-701c5e256137.png" align="right" width="100px" alt="">
<h2 align="left">Introduction</h2>

PaiGram based on [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)

![Alt](https://repobeats.axiom.co/api/embed/f73c1121006cb86196f83da2170242b7a97f8be0.svg "Repobeats analytics image")

[ZH README](/docs/README_ZH.md)

## System Dependencies

- Python 3.11+
- MySQL or SQLite
- Redis

## Usage

Depending on your preferred environment, follow one of the setups below:

### WSL2 Ubuntu 22.04 Setup

For contributors using WSL2 on Ubuntu 22.04, follow the [detailed guide here](/docs/wsl/EN.md).

### Standard Setup (All Environments)

#### 1. Clone PaiGram from Git

```bash
git clone git@github.com:PaiGramTeam/PaiGram.git
cd PaiGram/
git submodule update --init --recursive
```

#### 2. Project Setup

- It's recommended to use a virtual environment. You can set it up via `venv` or `virtualenv`.

**Create Virtual environment:**

```bash
python3 -m venv venv
```

**Activate the virtual environment:**

*For Linux:*

```bash
source venv/bin/activate
```

*For Windows Command Prompt:*

```bash
venv\Scripts\activate.bat
```

*For Windows PowerShell:*

```bash
.\venv\Scripts\Activate.ps1
```

**Install Dependencies**

```bash
pip install poetry
poetry install --extras all
playwright install chromium
```

Optional Dependencies

```bash
poetry install --extras all
```

**Edit Config**

Create a dotenv config (`.env`) based on the given example. Ensure to provide the necessary database connection
  details and bot token parameters.

```bash
cp .env.example .env
```

For detailed configurations, refer to the [Wiki/Env Settings](https://github.com/PaiGramTeam/PaiGram/wiki/Env-Settings).

#### 3. Database Setup with Alembic

```bash
alembic upgrade head
```

#### 4. Run PaiGram

Ensure the `venv` is still active:

```bash
python ./run.py
```

### Alternative Deployments

- **Docker:** For deployments using Docker, see
  the [Wiki/Deploy with Docker](https://github.com/PaiGramTeam/PaiGram/wiki/Deploy-with-Docker).

- **Podman:** For deployments using Podman, see
  the [Wiki/Deploy with Podman](https://github.com/PaiGramTeam/PaiGram/wiki/Deploy-with-Podman).

## Additional Information

This project is currently being expanded,
adding more entertainment and information query features related to Genshin Impact.
Stay tuned!

## Acknowledgments

|                                Nickname                                 | Introduce        |
|:-----------------------------------------------------------------------:|------------------|
|          [原神抽卡全机制总结](https://www.bilibili.com/read/cv10468091)          | 本项目抽卡模拟器使用的逻辑    |
| [西风驿站 猫冬](https://bbs.mihoyo.com/ys/accountCenter/postList?id=74019947) | 本项目攻略图图源         |
|           [Yunzai-Bot](https://github.com/Le-niao/Yunzai-Bot)           | 本项使用的抽卡图片和前端资源来源 |
|       [Crawler-ghhw](https://github.com/DGP-Studio/Crawler-ghhw)        | 本项目参考的爬虫代码       |
|                  [Enka.Network](https://enka.network)                   | 角色卡片的数据来源        |
|      [miao-plugin](https://github.com/yoimiya-kokomi/miao-plugin)       | 角色卡片的参考项目        |
