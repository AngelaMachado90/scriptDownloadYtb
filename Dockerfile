FROM python:3.12-slim

ARG DENO_VERSION=2.3.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg unzip \
    && curl --fail --location --silent --show-error \
        "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-x86_64-unknown-linux-gnu.zip" \
        --output /tmp/deno.zip \
    && unzip /tmp/deno.zip -d /usr/local/bin \
    && chmod 0755 /usr/local/bin/deno \
    && rm /tmp/deno.zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN deno --version && python -c "import importlib.metadata; print(importlib.metadata.version('yt-dlp-ejs'))"

COPY --chown=1000:1000 app.py youtubeVideos.py ./
COPY --chown=1000:1000 music_library ./music_library
COPY --chown=1000:1000 scripts ./scripts
RUN mkdir -p /app/downloads /app/logs && chown -R 1000:1000 /app

USER 1000:1000
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
