FROM python:3.8.11-alpine3.14 AS base

FROM base AS runtime_1
RUN apk add --no-cache g++                                \
    && python3 -m pip install virtualenv                  \
    && python3 -m poetry install --extras all             \
    && apk del g++

FROM runtime_1 AS runtime_2
RUN apk add --no-cache libstdc++


FROM base AS dependency
ADD https://raw.githubusercontent.com/eficode/wait-for/master/wait-for /wait-for
RUN chmod a+x /wait-for


FROM runtime_2
COPY . /root/app/
COPY --from=dependency /wait-for /wait-for
WORKDIR /root/app/
ENTRYPOINT echo "Waiting for database (sleep=25s)..." && sleep 25 \
    && echo "Waiting for API ${MYSQL_HOST}:${MYSQL_PORT} ${REDIS_HOST}:${REDIS_PORT}..." \
    && /wait-for ${MYSQL_HOST}:${MYSQL_PORT} ${REDIS_HOST}:${REDIS_PORT} -- \
     python3 -m pytest tests/integration