ARG PYTHON_VERSION=3.14.8

# Stage 1: Dependency resolution
FROM astral/uv:python3.14-bookworm-slim AS uv
WORKDIR /swi
COPY pyproject.toml uv.lock ./
# Export the locked, hashed set: the image installs exactly what uv.lock pins.
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt

# Stage 2: Build
FROM python:${PYTHON_VERSION}-slim AS builder
WORKDIR /swi
COPY --from=uv /swi/requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Stage 3: Runtime
FROM python:${PYTHON_VERSION}-slim
# The project reserves uids above 9000. Every SWI image that shares a volume with this one
# (the other cron jobs, mapproxy, the read-only data services) uses the same uid and gid,
# so files written here are owned by the same user everywhere.
ARG APP_UID=9001
ARG APP_GID=9001
WORKDIR /swi

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# The job never installs packages at runtime: remove pip (and its vendored copies of
# urllib3, msgpack, ...) so they are neither exposed nor flagged by image scanners.
RUN python -m pip uninstall -y pip setuptools wheel 2>/dev/null || true

# Unprivileged user with a home directory (entrypoint.sh writes ~/.bashrc)
RUN groupadd --gid "${APP_GID}" swi \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /usr/sbin/nologin swi

# The job downloads into ./data and writes into two volumes (./export and ./metadata).
# Create the mount points owned by the job user: an empty named volume inherits the
# ownership of the directory it is mounted on, so a fresh volume is writable without any
# runtime chown.
RUN mkdir -p /swi/export /swi/metadata \
    && chown swi:swi /swi /swi/export /swi/metadata

# The code stays owned by root: the job can create files here, not edit its own code
COPY icechart_caching.py ./run.py
COPY mapnik_map_file.xml ./mapnik_map_file.xml
COPY entrypoint.sh ./entrypoint.sh
COPY run-cron.sh ./run-cron.sh

# Make the entrypoint script executable
RUN chmod +x ./entrypoint.sh ./run-cron.sh

USER swi

# Use the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
