FROM python:3.9

COPY . /root/app/
WORKDIR /root/app/

ENV VIRTUAL_ENV=/root/app/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --upgrade poetry
RUN python3 -m poetry install --extras all

RUN ls -l

ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.9.0/wait /wait
RUN chmod +x /wait
CMD /wait && python3 -m pytest tests/integration