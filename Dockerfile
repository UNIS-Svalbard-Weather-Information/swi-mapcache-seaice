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
WORKDIR /swi

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# The job never installs packages at runtime: remove pip (and its vendored copies of
# urllib3, msgpack, ...) so they are neither exposed nor flagged by image scanners.
RUN python -m pip uninstall -y pip setuptools wheel 2>/dev/null || true

COPY icechart_caching.py ./run.py
COPY mapnik_map_file.xml ./mapnik_map_file.xml
COPY entrypoint.sh ./entrypoint.sh
COPY run-cron.sh ./run-cron.sh

# Make the entrypoint script executable
RUN chmod +x ./entrypoint.sh ./run-cron.sh

# Use the entrypoint script
ENTRYPOINT ["./entrypoint.sh"]
