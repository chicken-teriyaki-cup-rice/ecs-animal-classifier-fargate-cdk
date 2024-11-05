FROM --platform=linux/amd64 python:3.9-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM --platform=linux/amd64 python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=true \
    STREAMLIT_LOGGER_LEVEL=debug

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && useradd -m -s /bin/bash streamlit

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY --chown=streamlit:streamlit app.py ./

USER streamlit

RUN mkdir -p ~/.streamlit && \
    echo '\
    [server]\n\
    enableCORS = true\n\
    enableXsrfProtection = false\n\
    maxUploadSize = 5\n\
    headless = true\n\
    port = 8501\n\
    address = "0.0.0.0"\n\
    baseUrlPath = ""\n\
    [browser]\n\
    serverAddress = "0.0.0.0"\n\
    serverPort = 8501\n\
    gatherUsageStats = false\n\
    ' > ~/.streamlit/config.toml

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["streamlit", "run", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.baseUrlPath=", \
    "--server.enableCORS=true", \
    "--server.enableXsrfProtection=false", \
    "--server.headless=true", \
    "--logger.level=debug", \
    "app.py"]
