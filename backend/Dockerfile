FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system --gid 1001 appgroup \
    && useradd --system --uid 1001 --gid appgroup --create-home appuser

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    # Linux wheels from the default PyPI index can bring NVIDIA CUDA runtime packages. \
    # The local Docker deployment runs inference on CPU, so keep the image portable. \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && python -m pip install -r requirements.txt

COPY --chown=appuser:appgroup app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
