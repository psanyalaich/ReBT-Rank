# Container image for ReBT-Rank (Task A4).
#
# Option A (approved): the package is installed from pyproject.toml. The image is
# structured so a lockfile-pinned install can be dropped in later WITHOUT
# redesign (see the dependency-install section below).
#
# TECHNICAL DEBT (must be resolved before the first public release):
#   The environment is NOT yet pinned to a lockfile; dependencies are resolved
#   from pyproject.toml at build time. When an explicit lockfile task lands,
#   enable the lockfile COPY/RUN below and switch the package install to
#   `pip install --no-deps .`.

# Pinned Python 3.11 patch release on Debian bookworm (slim). Deliberately not
# SHA-digest pinned at this stage (per project decision); the patch tag may be
# advanced to a newer 3.11 security release as a deliberate, reviewed update.
FROM python:3.11.9-slim-bookworm

LABEL org.opencontainers.image.title="ReBT-Rank" \
      org.opencontainers.image.description="Calibrated, FDR-controlled re-ranking of reverse-biotransformation-derived metabolite-gene hypotheses." \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/psanyalaich/ReBT-Rank"

# Deterministic, quiet Python/pip behaviour.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /opt/rebt-rank

# --- Dependency + package installation ---------------------------------------
# Future lockfile hook (DO NOT enable until a lockfile actually exists):
#     COPY requirements.lock ./
#     RUN pip install --require-hashes -r requirements.lock
# and then change the package install below to `pip install --no-deps .`.
#
# README.md is required by the build backend (pyproject `readme` field); LICENSE
# is copied for image provenance.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

# Run as an unprivileged user.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# `docker run <image>` invokes the CLI; the default command shows help.
ENTRYPOINT ["rebt-rank"]
CMD ["--help"]
