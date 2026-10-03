FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY config ./config
ENV PYTHONPATH=/app/src RUDRILA_MODE=demo LIVE_TRADING=false PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "from rudrila.health import HealthState; x=HealthState().read(); assert x.get('status') not in ('fatal','unknown')"
CMD ["python","-m","rudrila.main","--demo-run","86400"]
