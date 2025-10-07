FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RESUME_DIR=/app/DB

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh \
    && useradd --system --no-create-home app \
    && mkdir -p /app/DB \
    && chown -R app /app/DB

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8000/api/health', headers={'Host': 'localhost'}), timeout=3)"
ENTRYPOINT ["./entrypoint.sh"]
