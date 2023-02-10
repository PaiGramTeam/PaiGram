FROM python:3.10.10-buster
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=zh_CN.UTF-8                               \
    SHELL=/bin/bash
SHELL ["/bin/bash", "-c"]
WORKDIR /app
RUN echo "deb http://ftp.us.debian.org/debian buster main non-free" >> /etc/apt/sources.list.d/fonts.list \
    && apt update                                     \
    # clone
    && apt install git wget curl -y                           \
    && git clone -b main https://github.com/luoshuijs/TGPaimonBot.git /app \
    # install dependencies \
    && pip install virtualenv poetry               \
    && python3 -m virtualenv venv/                 \
    && . venv/bin/activate                         \
    && poetry config virtualenvs.create false      \
    && poetry source add --default mirrors https://pypi.tuna.tsinghua.edu.cn/simple/ \
    && poetry install                              \
    && poetry install --extras all                 \
    && playwright install chromium                 \
    && playwright install-deps chromium            \
    ## set timezone
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone        \
    # create cache folder
    && mkdir cache/                                \
    # clean
    && apt-get clean -y                            \
    && rm -rf                                      \
        /tmp/*                                     \
        /var/lib/apt/lists/*                       \
        /var/tmp/*                                 \
        ~/.cache/pip                               \
        ~/.cache/pypoetry                          \
    # Add the wait script to the image
    && wget -O /wait https://github.com/ufoscout/docker-compose-wait/releases/download/2.9.0/wait \
    && chmod +x /wait
ENTRYPOINT /wait && venv/bin/alembic upgrade head && venv/bin/python run.py
