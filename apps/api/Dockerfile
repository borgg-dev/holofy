# Holofy API image. NOTE: not built in the dev sandbox (no Docker there); built + run in CI
# and on a Docker host. Runs migrations then serves uvicorn against the configured DB/Redis.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching. RapidOCR pulls in opencv-python, which links X11/GL
# system libs absent from the slim image (libGL, libxcb…). Swap it for opencv-python-headless,
# the same cv2 module without the GUI/X deps — the canonical fix for OpenCV in containers.
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && pip uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true \
    && pip install --no-cache-dir opencv-python-headless

COPY . .

# Run as a non-root user. Pre-create the capture-storage dir owned by that user so a freshly
# created named volume mounted there inherits the right ownership (otherwise the volume is
# root-owned and the non-root app can't write uploads — Errno 13).
RUN useradd --create-home --uid 10001 holofy \
    && mkdir -p /data/captures \
    && chown -R holofy /app /data
USER holofy

EXPOSE 8000

# Migrate, then serve. HOLOFY_DATABASE_URL / HOLOFY_REDIS_URL come from the environment.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
