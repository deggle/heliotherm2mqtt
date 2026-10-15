FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/deggle/heliotherm2mqtt" \
      org.opencontainers.image.description="Heliotherm heat pump (Modbus TCP) to MQTT bridge" \
      org.opencontainers.image.licenses="MIT"
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    pip install --no-cache-dir /wheels/*.whl \
 && useradd --system --no-create-home --uid 1000 heliotherm
ENV PYTHONUNBUFFERED=1 \
    H2M_CONFIG=/config/config.yaml
VOLUME /config
USER heliotherm
ENTRYPOINT ["heliotherm2mqtt"]
