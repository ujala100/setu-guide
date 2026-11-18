# syntax=docker/dockerfile:1
# Setu Guide API - Day 3 hardened image. Owner: DevOps 1.
# No secrets are baked in: every setting arrives at runtime from the
# environment (.env / docker-compose.yml). See .dockerignore.
#
# Day 3 security pass (docs/security_scan_report.md):
# - base pinned by digest (refresh deliberately, not silently)
# - no build tools in the final stage (pip/setuptools/wheel removed)
# - Debian fixes applied at build time where Debian ships them

# ---------------------------------------------------------------- builder
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The venv that ships to runtime keeps app dependencies only. Day 3 scan:
# pip/setuptools (plus setuptools' vendored wheel/jaraco.context) carried
# HIGH/MEDIUM CVEs - removing them clears those findings outright.
RUN pip uninstall -y pip setuptools

# ---------------------------------------------------------------- runtime
FROM python:3.11-slim@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Apply the Debian security updates that exist at build time (Day 3 scan:
# e.g. the liblzma5 DSA). CVEs without a Debian backport stay - they are
# listed with their mitigations in docs/security_scan_report.md.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Non-root user (no login shell, no home permissions needed).
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app

# No build tools in the final stage: the base image ships pip/setuptools/wheel
# globally, and they are not needed at runtime (absolute path - the venv pip
# was removed in the builder above).
RUN /usr/local/bin/pip uninstall -y pip setuptools wheel

# Model / knowledge-base files are NOT baked into the image (they are large and
# change independently). Mount them at runtime instead:
#   docker run -v ./models:/app/models:ro ...   (or /app/data)
# TODO(AI/ML): once those files are added, re-check `docker images` - the image
# size must stay small, so keep mounting them as a volume rather than COPYing.
RUN mkdir -p /app/models /app/data && chown -R app:app /app

USER app

EXPOSE 8000

# curl is not in slim images, so probe with the standard library.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# Day 4 recovery hardening (docs/recovery_test_notes.md):
# - --timeout-graceful-shutdown 30: on SIGTERM uvicorn stops accepting new
#   connections but lets in-flight requests finish. Without it the runtime
#   SIGKILLs a request that outlasts the stop window and the caller sees a
#   dropped connection instead of a reply or a clean fallback. 30s is a
#   superset of the request budget (LLM_TIMEOUT_SECONDS + 1s margin).
# - --timeout-keep-alive 5: an idle keep-alive connection is released after
#   5s so browsers/clients cannot hold the limited worker slots open.
# Keep these in sync with `stop_grace_period` in docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "30", "--timeout-keep-alive", "5"]
