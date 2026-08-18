# syntax=docker/dockerfile:1

FROM python:3.13-slim-bookworm AS builder

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels ".[mtproto]"


FROM rclone/rclone:1.75.0 AS rclone


FROM python:3.13-slim-bookworm

ARG VERSION=0.0.0
ARG REVISION=unknown

ENV HOME=/home/telegram2onedrive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.title="Telegram2OneDrive" \
      org.opencontainers.image.description="Transfer allowlisted Telegram files to OneDrive" \
      org.opencontainers.image.source="https://github.com/KurisuT7/Telegram2OneDrive" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="$VERSION" \
      org.opencontainers.image.revision="$REVISION"

RUN groupadd --gid 10001 telegram2onedrive \
    && useradd --no-log-init --uid 10001 --gid 10001 --create-home \
        --shell /usr/sbin/nologin telegram2onedrive

COPY --from=rclone /usr/local/bin/rclone /usr/local/bin/rclone
COPY --from=builder /wheels /wheels

RUN python -m pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels \
    && install -d -o 10001 -g 10001 -m 0700 \
        /config/rclone \
        /home/telegram2onedrive/.local/state/telegram2onedrive \
        /home/telegram2onedrive/.local/state/telegram2onedrive/mtproto \
    && touch /config/rclone/.volume-init \
        /home/telegram2onedrive/.local/state/telegram2onedrive/mtproto/.volume-init \
    && chown 10001:10001 \
        /config/rclone/.volume-init \
        /home/telegram2onedrive/.local/state/telegram2onedrive/mtproto/.volume-init

USER 10001:10001
WORKDIR /app

VOLUME ["/config/rclone", "/home/telegram2onedrive/.local/state/telegram2onedrive"]

ENTRYPOINT ["telegram2onedrive"]
CMD ["run"]
