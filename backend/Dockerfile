FROM --platform=linux/amd64 python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:32 \
    MALLOC_TRIM_THRESHOLD_=65536

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN python -m venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv

RUN $VIRTUAL_ENV/bin/pip install --upgrade pip

COPY requirements.txt .
RUN $VIRTUAL_ENV/bin/pip install --no-cache-dir \
    fastapi==0.95.0 \
    uvicorn[standard]==0.21.1 \
    websockets==10.4 \
    python-multipart==0.0.6 

RUN $VIRTUAL_ENV/bin/pip install "numpy==1.26.4" && \
    python -c "import numpy; print(f'Numpy version: {numpy.__version__}')"

RUN $VIRTUAL_ENV/bin/pip install --no-cache-dir \
    torch==2.0.0+cpu \
    torchvision==0.15.1+cpu \
    -f https://download.pytorch.org/whl/cpu/torch_stable.html \
    pillow==9.5.0

RUN useradd -m -s /bin/bash app

WORKDIR /app
RUN chown app:app /app

USER app

COPY --chown=app:app main.py ./

RUN for i in {1..3}; do \
    curl -o imagenet_class_index.json https://s3.amazonaws.com/deep-learning-models/image-models/imagenet_class_index.json && break || sleep 15; \
    done

RUN for i in {1..3}; do \
    python -c "import torch; from torchvision import models; models.resnet50(pretrained=True)" && break || sleep 15; \
    done

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--ws", "auto", \
    "--ws-ping-interval", "20", \
    "--ws-ping-timeout", "20", \
    "--proxy-headers", \
    "--forwarded-allow-ips", "*", \
    "--workers", "1", \
    "--timeout-keep-alive", "75"]
