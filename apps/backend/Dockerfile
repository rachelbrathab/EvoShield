# syntax=docker/dockerfile:1
# EvoShield backend — production-leaning image.
#
# Multi-stage, uv-managed deps, non-root runtime user, built-in healthcheck.
#
# IMPORTANT: this image ships the *actual scanner toolchain*, because the
# application is a multi-scanner orchestrator — without these binaries it
# cannot do its job. Pinned versions (verified release assets):
#   Trivy    v0.74.0  https://github.com/aquasecurity/trivy
#   Gitleaks v8.30.1  https://github.com/gitleaks/gitleaks
#   Syft     v1.51.1  https://github.com/anchore/syft
#   Grype    v0.118.0 https://github.com/anchore/grype
#   Semgrep  1.176.1  https://pypi.org/project/semgrep/
# Bump deliberately: verify the release asset URL still resolves, then
# re-run a real scan end-to-end (see docs/sprint-plans/015-sprint-8-*.md).
FROM python:3.12-slim AS builder

# uv pinned via pip: ghcr.io/astral-sh/uv does not publish version-prefixed
# tags, and a floating `latest` builder would undermine the pinning policy.
RUN pip install --no-cache-dir uv==0.11.33

WORKDIR /app

# Install dependencies first so the layer cache survives source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Runtime OS dependencies:
#   git        — repository acquisition clones with the system git
#   openssh-client — deploy-key acquisition clones over SSH (ssh-keygen,
#                ssh; ADR 0018)
#   ca-certificates, curl — TLS trust for scanner downloads + the healthcheck
#   libgcc-s1  — glibc runtime needed by the Go scanner binaries
#   procps     — `pkill` for subprocess cleanup guarantees
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        ca-certificates \
        curl \
        libgcc-s1 \
        procps \
    && rm -rf /var/lib/apt/lists/*

# ── Scanner binaries (single pinned release per tool, linux/amd64) ──────
ARG TARGETARCH
ARG TRIVY_VERSION=0.74.0
ARG GITLEAKS_VERSION=8.30.1
ARG SYFT_VERSION=1.51.1
ARG GRYPE_VERSION=0.118.0
ARG SEMGREP_VERSION=1.176.1

# Go-based scanners ship static tarballs from their GitHub releases.
RUN set -eux; \
    curl -fsSL -o /tmp/trivy.tar.gz \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"; \
    tar -xzf /tmp/trivy.tar.gz -C /usr/local/bin trivy; \
    curl -fsSL -o /tmp/gitleaks.tar.gz \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"; \
    tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks; \
    curl -fsSL -o /tmp/syft.tar.gz \
      "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz"; \
    tar -xzf /tmp/syft.tar.gz -C /usr/local/bin syft; \
    curl -fsSL -o /tmp/grype.tar.gz \
      "https://github.com/anchore/grype/releases/download/v${GRYPE_VERSION}/grype_${GRYPE_VERSION}_linux_amd64.tar.gz"; \
    tar -xzf /tmp/grype.tar.gz -C /usr/local/bin grype; \
    chmod 0755 /usr/local/bin/trivy /usr/local/bin/gitleaks /usr/local/bin/syft /usr/local/bin/grype; \
    rm -f /tmp/*.tar.gz

# Semgrep is a Python application — install it into its own virtualenv so
# its transitive dependencies can never clash with EvoShield's locked env.
RUN python -m venv /opt/semgrep-venv \
    && /opt/semgrep-venv/bin/pip install --no-cache-dir "semgrep==${SEMGREP_VERSION}" \
    && ln -s /opt/semgrep-venv/bin/semgrep /usr/local/bin/semgrep

# Verify every tool answers --version at build time; a broken layer fails
# the build instead of every future scan.
RUN trivy --version && gitleaks version && syft version && grype version && semgrep --version

# ── Application ─────────────────────────────────────────────────────────
# WORKDIR must precede the COPYs: relative destinations resolve against it.
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN groupadd --system app && useradd --system --gid app app

# Pre-create writable mount points with the runtime user's ownership
# (scanner DB cache, repository-clone workspace) and the user's home —
# Semgrep writes its user log to ~/.semgrep and crashes as a non-root user
# when the home directory does not exist.
RUN mkdir -p /tmp/scanner-cache /tmp/evoshield-scans /home/app/.semgrep \
    && chown -R app:app /tmp/scanner-cache /tmp/evoshield-scans /home/app

WORKDIR /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else 1)"]

# ENTRYPOINT (not CMD) so `docker run image <cmd>` still starts uvicorn;
# compose overrides command for the migrate-one-off pattern.
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
