FROM python:3.10.8-slim-bullseye
COPY . /app
WORKDIR /app
RUN pip install virtualenv poetry           \
    && python3 -m virtualenv venv/          \
    && . venv/bin/activate                  \
    && poetry install                       \
    && playwright install chromium          \
    && playwright install-deps              \
    && apt install -y git                   \
    && git init .                           \
    && git add -A                           \
    && git -c user.name='user'              \
           -c user.email='user@example.com' \
           commit -m 'Docker deployment'    \
    && mkdir cache/                         \
    && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["venv/bin/python", "./run.py"]
