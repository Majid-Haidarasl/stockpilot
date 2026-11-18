# StockPilot backup image: pg_dump (Postgres 17 client) + restic.
# Pin restic version; record in docs/architecture/versions.md.
FROM postgres:17

ARG RESTIC_VERSION=0.17.3
ARG TARGETARCH

USER root
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl bzip2; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) restic_arch=amd64 ;; \
      arm64) restic_arch=arm64 ;; \
      *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
      "https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/restic_${RESTIC_VERSION}_linux_${restic_arch}.bz2" \
      | bunzip2 > /usr/local/bin/restic; \
    chmod 755 /usr/local/bin/restic; \
    restic version; \
    apt-get purge -y curl bzip2; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*

COPY lib.sh backup.sh restore.sh scheduler.sh /usr/local/bin/
RUN chmod 755 /usr/local/bin/lib.sh /usr/local/bin/backup.sh \
      /usr/local/bin/restore.sh /usr/local/bin/scheduler.sh \
    && ln -sf /usr/local/bin/backup.sh /backup.sh \
    && ln -sf /usr/local/bin/restore.sh /restore.sh \
    && ln -sf /usr/local/bin/scheduler.sh /scheduler.sh

# Non-root uid 1000 (postgres image may already define a "backup" user).
RUN mkdir -p /var/lib/stockpilot/backup-scratch /var/lib/stockpilot/media \
             /var/lib/stockpilot/restic-practice \
    && chown -R 1000:1000 /var/lib/stockpilot

USER 1000:1000
WORKDIR /var/lib/stockpilot
ENTRYPOINT []
CMD ["/usr/local/bin/backup.sh"]
